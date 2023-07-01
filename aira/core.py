"""Core processing for AIRA module."""
import numpy as np
from dataclasses import dataclass
from plotly import graph_objects as go

from aira.engine.input import InputProcessorChain, InputMode
from aira.engine.intensity import (
    convert_bformat_to_intensity,
    analysis_crop_2d,
    integrate_intensity_directions,
    intensity_thresholding,
)
from aira.engine.pressure import w_channel_preprocess
from aira.engine.plot import hedgehog, w_channel, setup_plotly_layout, get_xy_projection
from aira.engine.reflections import detect_reflections
from aira.utils import read_signals_dict, cartesian_to_spherical


@dataclass
class AmbisonicsImpulseResponseAnalyzer:
    """Main class for analyzing Ambisonics impulse responses"""

    input_builder = InputProcessorChain()

    def analyze(
        self,
        input_dict: dict,
        integration_time: float,
        intensity_threshold: float,
        analysis_length: float,
        show: bool = False,
    ) -> go.Figure:
        """Analyzes a set of measurements in Ambisonics format and plots a hedgehog
        with the estimated reflections direction.

        Parameters
        ----------
        input_dict : dict
            Dictionary with all the data needed to analyze a set of measurements
            (paths of the measurements, input mode, channels per file, etc.)
        integration_time : float, optional
            Time frame where intensity vectors are integrated by the mean of them,
            by default INTEGRATION_TIME
        intensity_threshold : float, optional
            Bottom limit for intensity values in dB, by default INTENSITY_THRESHOLD
        analysis_length : float, optional
            Total time of analysis from intensity max peak, by default ANALYSIS_LENGTH
        show : bool, optional
            Shows plotly figure in browser, by default False

        Returns
        -------
        go.Figure
            Plotly figure with hedgehog and w-channel plot
        """

        signals_dict = read_signals_dict(input_dict)
        sample_rate = signals_dict["sample_rate"]

        bformat_signals = self.input_builder.process(input_dict)

        intensity_directions = convert_bformat_to_intensity(bformat_signals)

        intensity_directions_cropped = analysis_crop_2d(
            analysis_length, sample_rate, intensity_directions
        )

        intensity_windowed, time = integrate_intensity_directions(
            intensity_directions_cropped, integration_time, sample_rate
        )

        intensity, azimuth, elevation = cartesian_to_spherical(intensity_windowed)

        (
            intensity_peaks,
            azimuth_peaks,
            elevation_peaks,
            reflections_idx,
        ) = detect_reflections(intensity, azimuth, elevation)

        (
            reflex_to_direct,
            azimuth_peaks,
            elevation_peaks,
            reflections_idx,
        ) = intensity_thresholding(
            intensity_threshold,
            intensity_peaks,
            azimuth_peaks,
            elevation_peaks,
            reflections_idx,
        )

        time = time[reflections_idx]

        fig = setup_plotly_layout()

        hedgehog(fig, time, reflex_to_direct, azimuth_peaks, elevation_peaks)

        w_channel_signal = w_channel_preprocess(
            bformat_signals[0, :],
            int(integration_time * sample_rate),
            analysis_length,
            sample_rate,
        )

        w_channel(
            fig,
            np.arange(0, analysis_length, 1 / sample_rate) * 1000,
            w_channel_signal,
            intensity_threshold,
            time,
        )

        if show:
            fig.show()
        return fig

    def export_xy_projection(self, fig: go.Figure, img_name: str):
        new_fig = get_xy_projection(fig)
        new_fig.write_image(img_name, format="png")


if __name__ == "__main__":
    # Regio theater
    data = {
        "front_left_up": "test/mock_data/regio_theater/soundfield_flu.wav",
        "front_right_down": "test/mock_data/regio_theater/soundfield_frd.wav",
        "back_right_up": "test/mock_data/regio_theater/soundfield_bru.wav",
        "back_left_down": "test/mock_data/regio_theater/soundfield_bld.wav",
        "inverse_filter": "test/mock_data/regio_theater/soundfield_inverse_filter.wav",
        "input_mode": InputMode.LSS,
        "channels_per_file": 1,
        "frequency_correction": True,
    }

    # York auditorium
    # data = {
    #     "stacked_signals": "test/mock_data/york_auditorium/s2r2.wav",
    #     "input_mode": InputMode.BFORMAT,
    #     "channels_per_file": 4,
    #     "frequency_correction": False,
    # }
    integration_time = 0.01
    intensity_threshold = -50
    analysis_length = 0.3
    analyzer = AmbisonicsImpulseResponseAnalyzer()
    fig = analyzer.analyze(
        input_dict=data,
        integration_time=integration_time,
        intensity_threshold=intensity_threshold,
        analysis_length=analysis_length,
        show=True,
    )
    analyzer.export_xy_projection(fig, "projection.png")
