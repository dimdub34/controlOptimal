# -*- coding: utf-8 -*-

# built-in
import logging
from datetime import datetime
from twisted.internet import defer
from twisted.spread import pb  # because some functions can be called remotely
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, Float, Boolean, ForeignKey, DateTime
from PyQt4.QtCore import QTimer

# le2m
from server.servbase import Base
from server.servparties import Partie
from util.utiltools import get_module_attributes

# controlOptimal
import controlOptimalParams as pms


logger = logging.getLogger("le2m")


class PartieCO(Partie, pb.Referenceable):
    __tablename__ = "partie_controlOptimal"
    __mapper_args__ = {'polymorphic_identity': 'controlOptimal'}

    partie_id = Column(Integer, ForeignKey('parties.id'), primary_key=True)
    repetitions = relationship('RepetitionsCO')
    curves = relationship('CurveCO')

    CO_dynamic_type = Column(Integer)
    CO_trial = Column(Boolean)
    CO_sequence = Column(Integer)
    CO_treatment = Column(Integer)
    CO_group = Column(Integer, default=None)
    CO_gain_ecus = Column(Float)
    CO_gain_euros = Column(Float)

    def __init__(self, le2mserv, joueur, **kwargs):
        super(PartieCO, self).__init__(
            nom="controlOptimal", nom_court="CO",
            joueur=joueur, le2mserv=le2mserv)

        self.CO_sequence = kwargs.get("current_sequence", 0)
        self.CO_gain_ecus = 0
        self.CO_gain_euros = 0

        self.time_start = None
        self.timer_update = QTimer()
        self.timer_update.setInterval(
            int(pms.TIMER_UPDATE.total_seconds())*1000)
        self.timer_update.timeout.connect(self.update_data)

    @defer.inlineCallbacks
    def configure(self):
        logger.debug(u"{} Configure".format(self.joueur))
        self.CO_dynamic_type = pms.DYNAMIC_TYPE
        self.CO_treatment = pms.TREATMENT
        self.CO_trial = pms.PARTIE_ESSAI
        self.current_resource = pms.RESOURCE_INITIAL_STOCK
        # we send self because some methods are called remotely
        # we send also the group composition
        yield (self.remote.callRemote(
            "configure", get_module_attributes(pms), self))
        self.joueur.info(u"Ok")

    @defer.inlineCallbacks
    def newperiod(self, period):
        """
        Create a new period and inform the remote
        :param period:
        :return:
        """
        logger.debug(u"{} New Period".format(self.joueur))
        self.currentperiod = RepetitionsCO(period)
        self.le2mserv.gestionnaire_base.ajouter(self.currentperiod)
        self.repetitions.append(self.currentperiod)
        yield (self.remote.callRemote("newperiod", period))
        logger.info(u"{} Ready for period {}".format(self.joueur, period))

    @defer.inlineCallbacks
    def set_initial_extraction(self):
        """
        The player set his initial extraction, before to start the game
        :return:
        """
        self.time_start = datetime.now()  # needed by remote_new_extraction
        initial_extraction = yield (self.remote.callRemote(
            "set_initial_extraction"))
        self.remote_new_extraction(initial_extraction)
        self.joueur.remove_waitmode()

    @defer.inlineCallbacks
    def display_decision(self, time_start):
        """
        Display the decision screen on the remote
        Get back the decision
        :param time_start: the time the server starts
        :return:
        """
        logger.debug(u"{} Decision".format(self.joueur))
        self.time_start = time_start
        extraction = yield (self.remote.callRemote(
            "display_decision", self.time_start))
        self.currentperiod.CO_decisiontime = \
            (datetime.now() - self.time_start).total_seconds()
        if pms.DYNAMIC_TYPE == pms.DISCRETE:
            self.remote_new_extraction(extraction)
        self.joueur.remove_waitmode()

    def remote_new_extraction(self, extraction):
        """
        Called by the remote when the subject makes an extraction in the
        continuous treatment
        :param extraction:
        :return:
        """
        self.current_extraction = ExtractionsCO(
            extraction, int((datetime.now() - self.time_start).total_seconds()))
        self.joueur.info(self.current_extraction)
        self.le2mserv.gestionnaire_base.ajouter(self.current_extraction)
        self.currentperiod.extractions.append(self.current_extraction)

    def update_data(self):
        # after the initial extraction but before the game starts
        # self.time_start is None
        try:
            the_time = int((datetime.now() - self.time_start).total_seconds())
        except TypeError:
            the_time = 0

        # ----------------------------------------------------------------------
        # compute the resource
        # ----------------------------------------------------------------------
        self.current_resource += pms.RESOURCE_GROWTH
        # if the extraction > current_resource we create a new extraction of 0
        if self.current_extraction.CO_extraction > self.current_resource:
            # create a new extraction
            self.current_extraction = ExtractionsCO(0, the_time)
            self.joueur.info(self.current_extraction)
            self.le2mserv.gestionnaire_base.ajouter(self.current_extraction)
            self.currentperiod.extractions.append(self.current_extraction)
        self.current_resource -= self.current_extraction.CO_extraction
        self.current_extraction.CO_resource = self.current_resource

        # ----------------------------------------------------------------------
        # compute individual payoffs
        # ----------------------------------------------------------------------
        try:
            j_extrac = self.current_extraction.CO_extraction
            self.current_extraction.CO_benefice = \
                pms.param_a * j_extrac - (pms.param_b / 2) * pow(j_extrac, 2)
            self.current_extraction.CO_cost = \
                j_extrac * (pms.param_c0 - pms.param_c1 * self.current_resource)
            # we do not allow a negative cost
            if self.current_extraction.CO_cost < 0:
                self.current_extraction.CO_cost = 0
            self.current_extraction.CO_payoff = \
                self.current_extraction.CO_benefice - self.current_extraction.CO_cost
        except KeyError:
            pass  # only for the initial extraction

        # ----------------------------------------------------------------------
        # update the remote
        # ----------------------------------------------------------------------
        self.remote.callRemote(
            "update_data", self.current_extraction.to_dict(), the_time)

    @defer.inlineCallbacks
    def end_update_data(self):
        yield (self.remote.callRemote("end_update_data"))

    # def compute_periodpayoff(self):
    #     logger.debug(u"{} Period Payoff".format(self.joueur))
    #     self.currentperiod.CO_periodpayoff = 0
    #
    #     # cumulative payoff since the first period
    #     if self.currentperiod.CO_period < 2:
    #         self.currentperiod.CO_cumulativepayoff = \
    #             self.currentperiod.CO_periodpayoff
    #     else:
    #         previousperiod = self.periods[self.currentperiod.CO_period - 1]
    #         self.currentperiod.CO_cumulativepayoff = \
    #             previousperiod.CO_cumulativepayoff + \
    #             self.currentperiod.CO_periodpayoff
    #
    #     # we store the period in the self.periodes dictionnary
    #     self.periods[self.currentperiod.CO_period] = self.currentperiod
    #
    #     logger.debug(u"{} Period Payoff {}".format(
    #         self.joueur,
    #         self.currentperiod.CO_periodpayoff))

    @defer.inlineCallbacks
    def display_summary(self, *args):
        """
        Send a dictionary with the period content values to the remote.
        The remote creates the text and the history
        :param args:
        :return:
        """
        logger.debug(u"{} Summary".format(self.joueur))

        # ----------------------------------------------------------------------
        # we collect the x_data and y_data of the curves displayed on the
        # remote
        # ----------------------------------------------------------------------
        data_indiv = yield(self.remote.callRemote(
            "display_summary", self.currentperiod.to_dict()))

        extrac_indiv = data_indiv["extractions"]
        for x, y in extrac_indiv:
            curve_data = CurveCO(pms.EXTRACTION, x, y)
            self.le2mserv.gestionnaire_base.ajouter(curve_data)
            self.curves.append(curve_data)

        payoff_indiv = data_indiv["payoffs"]
        for x, y in payoff_indiv:
            curve_data = CurveCO(pms.PAYOFF, x, y)
            self.le2mserv.gestionnaire_base.ajouter(curve_data)
            self.curves.append(curve_data)
        # we collect the part payoff
        self.CO_gain_ecus = payoff_indiv[-1][1]

        resource = data_indiv["resource"]
        for x, y in resource:
            curve_data = CurveCO(pms.RESOURCE, x, y)
            self.le2mserv.gestionnaire_base.ajouter(curve_data)
            self.curves.append(curve_data)

        cost = data_indiv["cost"]
        for x, y in cost:
            curve_data = CurveCO(pms.COST, x, y)
            self.le2mserv.gestionnaire_base.ajouter(curve_data)
            self.curves.append(curve_data)

        self.joueur.info("Ok")
        self.joueur.remove_waitmode()

    @defer.inlineCallbacks
    def compute_partpayoff(self):
        """
        Compute the payoff for the part and set it on the remote.
        The remote stores it and creates the corresponding text for display
        (if asked)
        :return:
        """
        logger.debug(u"{} Part Payoff".format(self.joueur))

        self.CO_gain_euros = float("{:.2f}".format(float(self.CO_gain_ecus) *
                                                   float(pms.TAUX_CONVERSION)))

        yield (self.remote.callRemote(
            "set_payoffs", self.CO_gain_euros, self.CO_gain_ecus))

        logger.info(u'{} Payoff ecus {:.2f} Payoff euros {:.2f}'.format(
            self.joueur, self.CO_gain_ecus, self.CO_gain_euros))


# ==============================================================================
# REPETITIONS
# ==============================================================================

class RepetitionsCO(Base):
    __tablename__ = 'partie_controlOptimal_repetitions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    partie_partie_id = Column(Integer, ForeignKey("partie_controlOptimal.partie_id"))
    extractions = relationship('ExtractionsCO')

    CO_period = Column(Integer)
    CO_period_start_time = Column(DateTime, default=datetime.now)
    CO_decision = Column(Integer, default=0)
    CO_decisiontime = Column(Integer, default=0)
    CO_periodpayoff = Column(Float, default=0)
    CO_cumulativepayoff = Column(Float, default=0)

    def __init__(self, period):
        self.CO_period = period

    @property
    def number(self):
        return self.CO_period

    def to_dict(self, joueur=None):
        temp = {c.name: getattr(self, c.name) for c in self.__table__.columns
                if "CO" in c.name}
        if joueur:
            temp["joueur"] = joueur
        return temp


# ==============================================================================
# EXTRACTIONS
# we save each individual extraction
# ==============================================================================

class ExtractionsCO(Base):
    """
    In each period the subject can do several extractions in the continuous time
    treatment
    """
    __tablename__ = "partie_controlOptimal_extractions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    repetitions_id = Column(Integer, ForeignKey("partie_controlOptimal_repetitions.id"))
    CO_extraction = Column(Float)
    CO_extraction_time = Column(Float)
    CO_resource = Column(Float)
    CO_benefice = Column(Float)
    CO_cost = Column(Float)
    CO_payoff = Column(Float)

    def __init__(self, extraction, the_time):
        self.CO_extraction = extraction
        self.CO_extraction_time = the_time

    def __repr__(self):
        return "extraction: {}".format(self.CO_extraction)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


# ==============================================================================
# CURVES
# when the part is over, we save each curve
# ==============================================================================

class CurveCO(Base):
    __tablename__ = "partie_controlOptimal_curves"
    id = Column(Integer, primary_key=True, autoincrement=True)
    partie_id = Column(Integer, ForeignKey("partie_controlOptimal.partie_id"))
    CO_curve_type = Column(Integer)
    CO_curve_x = Column(Integer)
    CO_curve_y = Column(Float)

    def __init__(self, c_type, x, y):
        self.CO_curve_type = c_type
        self.CO_curve_x = x
        self.CO_curve_y = y


