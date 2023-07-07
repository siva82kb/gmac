"""
Other miscellaneous functions for GMAC analysis.
"""

import sys
import pathlib
import numpy as np
import pandas as pd
from scipy import signal
from ahrs.filters import Madgwick
from ahrs.common import orientation


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


def get_continuous_segments(df):
    # returns a list of continuous sections (as dataframes) from the original dataframe

    time_diff = np.array([pd.Timedelta(diff).total_seconds()
                          for diff in np.diff(df.index.values)])
    inx = np.sort(np.append(np.where(time_diff > 60)[0], -1))
    dfs = [df.iloc[inx[i] + 1:inx[i + 1] + 1]
           if i + 1 < len(inx)
           else df.iloc[inx[-1] + 1:]
           for i in np.arange(len(inx))]
    return dfs


def compute_vector_magnitude(imudf: pd.DataFrame) -> pd.DataFrame:
    """Computes the vector magnitude from the IMU data.
    """
    imudf = imudf.loc[:, ['ax', 'ay', 'az', 'gx', 'gy', 'gz']]
    imudf = resample(imudf, 30)
    op_df = pd.DataFrame(index=imudf.index)

    gyr = np.array(imudf[['gx', 'gy', 'gz']])
    acc = np.array(imudf[['ax', 'ay', 'az']])

    g = np.array([0, 0, 1])
    ae = np.empty([len(acc), 3])

    mg = Madgwick(frequency=30, beta=0.5)
    q = np.tile([1., 0., 0., 0.], (len(acc), 1))

    r = orientation.q2R(mg.updateIMU(q[0], gyr[0], acc[0]))
    ae[0] = np.matmul(r, acc[0]) - g

    for i in range(1, len(acc)):
        q[i] = mg.updateIMU(q[i - 1], gyr[i], acc[i])
        r = orientation.q2R(q[i])
        ae[i] = np.matmul(r, acc[i]) - g

    op_df['ax'] = bandpass(np.nan_to_num(ae[:, 0]), fs=30)
    op_df['ay'] = bandpass(np.nan_to_num(ae[:, 1]), fs=30)
    op_df['az'] = bandpass(np.nan_to_num(ae[:, 2]), fs=30)
    op_df = resample(op_df, 10)

    op_df['ax'] = np.where(np.absolute(op_df['ax'].values) < 0.068, 0, op_df['ax'].values) / 0.01664
    op_df['ay'] = np.where(np.absolute(op_df['ay'].values) < 0.068, 0, op_df['ay'].values) / 0.01664
    op_df['az'] = np.where(np.absolute(op_df['az'].values) < 0.068, 0, op_df['az'].values) / 0.01664

    dfs = get_continuous_segments(op_df)
    dfs = [df.resample(str(1) + 'S').sum() for df in dfs]
    op_df = pd.concat(dfs)
    op_df.index.name = 'time'
    op_df = op_df.fillna(0)

    op_df['a_mag'] = [np.linalg.norm(x) for x in np.array(op_df[['ax', 'ay', 'az']])]
    op_df['counts'] = [np.round(x) for x in op_df['a_mag'].rolling(5).mean()]
    return op_df[['counts']]


def resample(df, new_fs):
    dfs = get_continuous_segments(df)
    dfs = [df.resample(f'{str(round(1 / new_fs, 2))}S', label='right', closed='right').mean()
           for df in dfs]
    df = pd.concat(dfs)
    df.index.name = 'time'
    return df


def bandpass(x, fs=50, order=4):
    sos = signal.butter(order, [0.25, 2.5], 'bandpass', fs=fs, output='sos', analog=False)
    filtered = signal.sosfilt(sos, x)
    return filtered
