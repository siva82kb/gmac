
"""Module for with functions for computing gmac and analysing data from 
daily life.

Author: Sivakumar Balasubramanian
"""

import numpy as np
import pandas as pd
from scipy import signal


def estimate_pitch(accl_farm: np.array, nwin: int) -> np.array:
    """
    Estimates the pitch angle of the forearm from the accelerometer data.
    """
    # Moving averaging using the causal filter
    acclf = signal.lfilter(np.ones(nwin) / nwin, 1, accl_farm) if nwin > 1 else accl_farm
    acclf[acclf < -1] = -1
    acclf[acclf > 1] = 1        
    return -np.rad2deg(np.arccos(acclf)) + 90


def estimate_accl_mag(accl: np.array, fs: float, fc: float, nc: int,
                      deadband_th: float, n_am: int) -> np.array:
    """
    Compute the magnitude of the accelerometer signal.
    """
    # Highpass filter the acceleration data.
    sos = signal.butter(nc, fc, btype='highpass', fs=fs, output='sos')
    accl_filt = np.array([signal.sosfilt(sos, accl[:, 0]),
                          signal.sosfilt(sos, accl[:, 1]),
                          signal.sosfilt(sos, accl[:, 2])]).T
    
    # Zero load acceleration components.
    accl_filt[np.abs(accl_filt) < deadband_th] = 0
    
    # Acceleration magnitude    
    amag = np.linalg.norm(accl_filt, axis=1)
    
    # Moving average filter
    _input = np.append(np.ones(n_am - 1) * amag[0], amag)
    _impresp = np.ones(n_am) / n_am
    return np.convolve(_input, _impresp, mode='valid')


def estimate_gmac(accl: np.array, accl_farm_inx: int, Fs: float, params: dict) -> np.array:
    """
    Estimate GMAC for the given acceleration data and parameters.
    """
    # Estimate pitch and acceleration magnitude
    pitch = estimate_pitch(accl[:, accl_farm_inx], params["np"])
    accl_mag = estimate_accl_mag(accl, Fs, fc=params["fc"], nc=params["nc"],
                                 deadband_th=params["deadband_th"],
                                 n_am=params["nam"])
    
    # Compute GMAC
    _pout = 1.0 * (pitch >= params["p_th"])
    _amout = 1.0 * (accl_mag >= params["am_th"])
    return _pout * _amout

