# -*- coding: utf-8 -*-

"""=============================================================================
This modules contains the variables and the parameters.
Do not change the variables.
Parameters that can be changed without any risk of damages should be changed
by clicking on the configure sub-menu at the server screen.
If you need to change some parameters below please be sure of what you do,
which means that you should ask to the developer ;-)
============================================================================="""

from datetime import timedelta
import numpy as np

# ------------------------------------------------------------------------------
# VARIABLES - do not change any value below
# ------------------------------------------------------------------------------

BASELINE = 0
TREATMENTS_NAMES = {BASELINE: "Baseline"}

# used to set DYNCPR_dynamic_type
CONTINUOUS = 0
DISCRETE = 1
IMPULSORY = 2  # future

# used to store the curve (DYNCRP_curve_type)
EXTRACTION = 0
PAYOFF = 1
RESOURCE = 2

# ------------------------------------------------------------------------------
# PARAMETERS
# ------------------------------------------------------------------------------

TREATMENT = BASELINE  # for future treatments
TAUX_CONVERSION = 1
NOMBRE_PERIODES = 2  # only for dynamic == discrete
TAILLE_GROUPES = 2  # should not be changed without asking Dimitri
MONNAIE = u"ecu"

# DECISION
DECISION_MIN = 0
DECISION_MAX = 10
DECISION_STEP = 0.01

PARTIE_ESSAI = False

DYNAMIC_TYPE = CONTINUOUS
# continuous game
CONTINUOUS_TIME_DURATION = timedelta(seconds=60)  # can be changed in config screen
# time for the player to take a decision
DISCRETE_DECISION_TIME = timedelta(seconds=10)
# milliseconds
TIMER_UPDATE = timedelta(seconds=1)  # refresh the group data and the graphs

# ------------------------------------------------------------------------------
# RESOURCE
# ------------------------------------------------------------------------------

RESOURCE_INITIAL_STOCK = 10
RESOURCE_GROWTH = 0.56

# ------------------------------------------------------------------------------
# FONCTION DE GAIN
# ------------------------------------------------------------------------------

param_a = 2.5
param_b = 1.8
param_c0 = 2
param_c1 = 0.1
param_r = 0.05
param_tau = 0.1


def get_infinite_payoff(p, E_p, R_p):
    """
    Compute the payoff of the player if the group extraction stay at its
    current level at the infinite
    :param dyn_type: DISCRETE or CONTINUOUS
    :param p: the current period
    :param E_p: the current extraction value of the player
    :param G_p: the current extraction value of the group
    :param H_p: the current resource stock
    :return:
    """
    if DYNAMIC_TYPE == DISCRETE:
        pass  # todo: infinite payoff discrete dynamic_type

    elif DYNAMIC_TYPE == CONTINUOUS:
        cste_p = RESOURCE_GROWTH - E_p
        return np.asscalar((np.exp(-param_r*p) / param_r) *
               (param_a*E_p - (param_b/2) * E_p**2 -
                E_p*(param_c0 - param_c1 * R_p + param_c1 * cste_p * p)) +
                E_p * param_c1 * cste_p * \
               ((1+param_r*p) * np.exp(-param_r*p)/param_r**2))

