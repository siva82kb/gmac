"""
Other miscellaneous functions for GMAC analysis.
"""

import sys
import pathlib
import numpy as np
import pandas as pd
from scipy import signal


def compute_tilt(accl_farm: np.array, nwin: int) -> np.array:
    # Moving averaging using the Savitzky-Golay filter
    af = signal.savgol_filter(accl_farm, window_length=nwin, polyorder=0,
                              mode='constant')
    af[af < -1] = -1
    af[af > 1] = 1
    return -np.rad2deg(np.arccos(af)) + 90


def read_data(subject_type, base_path="../data/") -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Reads raw data from 'subject_type' folder
    """
    if subject_type == 'patient':
        left = pd.read_csv(pathlib.Path(base_path, subject_type, "affected.csv"),
                           parse_dates=['time'], index_col='time')
        right = pd.read_csv(pathlib.Path(base_path, subject_type, "unaffected.csv"),
                            parse_dates=['time'], index_col='time')
    elif subject_type == 'control':
        left = pd.read_csv(pathlib.Path(base_path, subject_type, "left.csv"),
                           parse_dates=['time'], index_col='time')
        right = pd.read_csv(pathlib.Path(base_path, subject_type, "right.csv"),
                            parse_dates=['time'], index_col='time')
    else:
        raise Exception(f"Invalid parameter: {subject_type}. Use 'control' or 'patient' instead.")
    return left, right


def get_largest_continuous_segment_indices(data: pd.DataFrame, subject: int,
                                           deltaT: np.timedelta64) -> tuple[int, int]:
    """
    Returns the indices of the longest continuous segment of data for the
    given subject.
    """
    _dtimes = np.diff(data[data.subject == subject].index)
    _jumpinx = np.hstack(([0], np.where(_dtimes > deltaT)[0]))
    _inx1 = np.argmax(np.diff(_jumpinx))
    return _jumpinx[_inx1], _jumpinx[_inx1 + 1] + 1


def get_segmented_data(data: pd.DataFrame, deltaT: np.timedelta64) -> dict[int, pd.DataFrame]:
    """
    Returns the segmented data for each subject in the given data.
    """
    # Go through each subject and get the longest continuous segments of data
    subjs = np.unique(data.subject)
    # Segment left data
    _subjdata = {}
    for _subj in subjs:
        # Get indices of the longest continuous segment of data
        inx = get_largest_continuous_segment_indices(data, _subj, deltaT)
        _subjdata[_subj] = data[data.subject == _subj].iloc[inx[0]:inx[1]]
    return _subjdata