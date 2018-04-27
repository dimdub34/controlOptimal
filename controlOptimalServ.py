# -*- coding: utf-8 -*-

# built-in
import logging
from collections import OrderedDict
from twisted.internet import defer
from datetime import datetime
from PyQt4.QtCore import QTimer, QObject, pyqtSlot
from PyQt4.QtGui import QMessageBox

# le2m
from util import utiltools
from util.utili18n import le2mtrans
from util.utiltools import get_module_attributes, timedelta_to_time
from server.servgui.servguidialogs import DSequence, GuiPayoffs

# controlOptimal
import controlOptimalParams as pms
from controlOptimalTexts import trans_CO
from controlOptimalGui import DConfigure


logger = logging.getLogger("le2m.{}".format(__name__))


class Serveur(object):
    def __init__(self, le2mserv):
        self.le2mserv = le2mserv
        self.current_sequence = 0
        self.current_period = 0
        self.all = []

        # creation of the menu (will be placed in the "part" menu on the
        # server screen)
        actions = OrderedDict()
        actions[le2mtrans(u"Configure")] = self.configure
        actions[le2mtrans(u"Display parameters")] = \
            lambda _: self.le2mserv.gestionnaire_graphique. \
            display_information2(
                utiltools.get_module_info(pms), le2mtrans(u"Parameters"))
        actions[le2mtrans(u"Start")] = lambda _: self.demarrer()
        actions[le2mtrans(u"Display payoffs")] = \
            lambda _: self.display_payoffs()
        self.le2mserv.gestionnaire_graphique.add_topartmenu(
            u"Contrôle Optimal", actions)

    def configure(self):
        screen_conf = DConfigure(self.le2mserv.gestionnaire_graphique.screen)
        if screen_conf.exec_():
            pms_list = []
            for k, v in get_module_attributes(pms).items():
                if k in ["DYNAMIC_TYPE", "NOMBRE_PERIODES", "PARTIE_ESSAI"]:
                    pms_list.append("{}: {}".format(k, v))
            continuous_time_duration = timedelta_to_time(pms.CONTINUOUS_TIME_DURATION)
            pms_list.append("CONTINUOUS_TIME_DURATION: {}".format(
                continuous_time_duration.strftime("%H:%M:%S")))
            self.le2mserv.gestionnaire_graphique.infoserv(pms_list)

    @defer.inlineCallbacks
    def demarrer(self):
        # ----------------------------------------------------------------------
        # check conditions
        # ----------------------------------------------------------------------

        if not self.le2mserv.gestionnaire_graphique.question(
                        le2mtrans("Start") + " Control Optimal?"):
            return

        # ----------------------------------------------------------------------
        # init part
        # ----------------------------------------------------------------------

        self.current_sequence += 1
        self.current_period = 0

        # __ creates parts ___
        yield (self.le2mserv.gestionnaire_experience.init_part(
            "controlOptimal", "PartieCO", "RemoteCO", pms,
            current_sequence=self.current_sequence))
        self.all = self.le2mserv.gestionnaire_joueurs.get_players(
            'controlOptimal')

        # __ set parameters on remotes (has to be after group formation) __
        yield (self.le2mserv.gestionnaire_experience.run_step(
            le2mtrans(u"Configure"), self.all, "configure"))

        # ----------------------------------------------------------------------
        # SELECT THE INITIAL EXTRACTION
        # ----------------------------------------------------------------------

        self.le2mserv.gestionnaire_experience.run_func(self.all, "newperiod", 0)
        yield (self.le2mserv.gestionnaire_experience.run_step(
            trans_CO(u"Initial extraction"), self.all, "set_initial_extraction"))
        self.le2mserv.gestionnaire_experience.run_func(
            self.all, "update_data")

        # ----------------------------------------------------------------------
        # DEPENDS ON TREATMENT
        # ----------------------------------------------------------------------

        if pms.DYNAMIC_TYPE == pms.CONTINUOUS:

            txt = le2mtrans(u"Period") + u" 1"
            self.le2mserv.gestionnaire_graphique.infoserv(
                txt, fg="white", bg="gray")
            self.le2mserv.gestionnaire_graphique.infoclt(
                txt, fg="white", bg="gray")
            yield (self.le2mserv.gestionnaire_experience.run_func(
                self.all, "newperiod", 1))

            # __ timer continuous part __
            QTimer.singleShot(
                pms.CONTINUOUS_TIME_DURATION.total_seconds()*1000 + 1000,
                self.slot_time_elapsed)
            time_start = datetime.now()
            self.le2mserv.gestionnaire_graphique.infoserv(
                "Start time: {}".format(time_start.strftime("%H:%M:%S")))
            for j in self.all:
                j.time_start = time_start
                j.timer_update.start()
            yield(self.le2mserv.gestionnaire_experience.run_step(
                trans_CO("Decision"), self.all, "display_decision",
                time_start))

        elif pms.DYNAMIC_TYPE == pms.DISCRETE:

            for period in range(1, pms.NOMBRE_PERIODES + 1):

                if self.le2mserv.gestionnaire_experience.stop_repetitions:
                    break

                # init period
                txt = le2mtrans(u"Period") + u" {}".format(period)
                self.le2mserv.gestionnaire_graphique.infoserv(
                    [txt], fg="white", bg="gray")
                self.le2mserv.gestionnaire_graphique.infoclt(
                    [txt], fg="white", bg="gray")
                yield (self.le2mserv.gestionnaire_experience.run_func(
                    self.all, "newperiod", period))

                # decision
                time_start = datetime.now()
                yield(self.le2mserv.gestionnaire_experience.run_step(
                    "Decision", self.all, "display_decision", time_start))

                self.le2mserv.gestionnaire_experience.run_func(
                    self.all, "update_data")

            self.slot_time_elapsed()

        # ----------------------------------------------------------------------
        # summary
        # ----------------------------------------------------------------------

        yield(self.le2mserv.gestionnaire_experience.run_step(
            le2mtrans(u"Summary"), self.all, "display_summary"))
        
        # ----------------------------------------------------------------------
        # End of part
        # ----------------------------------------------------------------------

        yield (self.le2mserv.gestionnaire_experience.finalize_part("controlOptimal"))

    @defer.inlineCallbacks
    @pyqtSlot()
    def slot_time_elapsed(self):
        self.le2mserv.gestionnaire_graphique.infoserv("End time: {}".format(
            datetime.now().strftime("%H:%M:%S")))
        for j in self.all:
            j.timer_update.stop()
        yield (self.le2mserv.gestionnaire_experience.run_func(
            self.all, "end_update_data"))

    def display_payoffs(self):
        sequence_screen = DSequence(self.current_sequence)
        if sequence_screen.exec_():
            sequence = sequence_screen.sequence
            players = self.le2mserv.gestionnaire_joueurs.get_players()
            payoffs = sorted([(j.hostname, p.DYNCPR_gain_euros) for j in players
                       for p in j.parties if p.nom == "controlOptimal" and
                       p.CO_sequence == sequence])
            logger.debug(payoffs)
            screen_payoffs = GuiPayoffs(self.le2mserv, "controlOptimal", payoffs)
            screen_payoffs.exec_()
