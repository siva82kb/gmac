"""
Other miscellaneous functions for GMAC analysis.
"""

import sys
import pathlib
import numpy as np
import pandas as pd
from scipy import signal


def computer_tilt_for_all_subjects(alldf: pd.DataFrame, accl_lbl: str, nwin: int) -> dict:
    """
    Computes the tilt angle for all subjects in the given dataframe.
    """
    return {
        _subj: np.hstack([
            compute_tilt(alldf.loc[(alldf.loc[:, 'subject'] == _subj) &
                                   (alldf.loc[:, 'segment'] == seg), accl_lbl], nwin)
            for seg in alldf.loc[alldf.loc[:, 'subject'] == _subj, 'segment'].unique()])
        for _subj in np.unique(alldf.subject)
    }


def compute_tilt(accl_farm: np.array, nwin: int) -> np.array:
    """
    Computes the tilt angle from the accelerometer data.
    """
    # Moving averaging using the Savitzky-Golay filter
    acclf = signal.savgol_filter(accl_farm, window_length=nwin, polyorder=0,
                                 mode='constant')
    acclf[acclf < -1] = -1
    acclf[acclf > 1] = 1
    return -np.rad2deg(np.arccos(acclf)) + 90


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
        raise ValueError(f"Invalid parameter: {subject_type}. Use 'control' or 'patient' instead.")
    return left, right


def assign_segments(df: pd.DataFrame, dur_th:float = 1, dT: float = 0.02) -> pd.DataFrame:
    """
    Assign a semgment column to the given dataframe, while removing segments
    shorter than 'dur_th' seconds.
    """
    # Get semgent indices
    _dtimes = np.array([pd.Timedelta(_dt).total_seconds()
                        for _dt in np.diff(df.index.values)])
    inx = np.hstack((0, np.where(_dtimes > dT)[0] + 1, len(df)))
    seginx = list(zip(inx[0:-1], inx[1:]))

    # Filter segments based on segment duration. Anything shorter than 5s is out.
    seginx = [ix for ix in seginx
            if pd.Timedelta(df.index[ix[1]-1] - df.index[ix[0]]).total_seconds() > dur_th]

    # Create new dataframe without short segments
    df = df.iloc[np.hstack([np.arange(ix[0], ix[1]) for ix in seginx])]

    # Assign segment column
    _segdf = pd.DataFrame(
        {"segment": np.hstack([[i] * (ix[1] - ix[0]) for i, ix in enumerate(seginx)])},
        index=df.index
    )
    
    return pd.concat([df, _segdf], axis=1)


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