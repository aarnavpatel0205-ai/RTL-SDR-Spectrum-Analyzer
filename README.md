# RTL-SDR Spectrum Analyzer
Real-time SDR-based spectrum analyzer in Python (PyQt6 + RTL-SDR) with waterfall, PSD, and time-domain views.

# RTL-SDR Spectrum Analyzer

A real-time RF spectrum analyzer built in Python, using an RTL-SDR Blog V3 dongle to capture and visualize live radio signals.

<img width="2500" height="1725" alt="image" src="https://github.com/user-attachments/assets/b4829d5d-267b-4e2f-9a8d-c02739f0865a" />
<img width="2500" height="1725" alt="image" src="https://github.com/user-attachments/assets/9b6b85cb-0533-49b2-9a3f-5c79988828ba" />


## Features

- **Time-domain plot** — raw IQ signal visualization over time
- **Amplitude vs. frequency plot** — real-time frequency-domain view
- **Power Spectral Density (PSD)** — signal power distribution across frequency
- **Spectrogram / waterfall display** — frequency content over time, useful for tracking intermittent or frequency-hopping signals
- Multi-threaded acquisition pipeline for smooth, responsive real-time rendering
- Configurable sample rate, center frequency, and FFT size (resolution bandwidth / video bandwidth)

## Hardware

- [RTL-SDR Blog V3](https://www.rtl-sdr.com/) dongle
- Dipole antenna (included in the RTL-SDR Blog dipole kit)

**Frequency range:** 15 MHz – 1.766 GHz (up to 24 MHz in direct sampling mode)

**Supported sample rates:** 0.5e6, 1e6, 1.25e6, 1.5e6, 1.75e6, 2e6, 2.048e6, 2.25e6, 2.4e6, 2.5e6, 2.75e6, 3e6, 3.2e6 (Hz)
> Note: stable performance validated up to 2.4 MSPS — higher rates may cause sample drops depending on USB throughput.

## Software / Tech Stack

- **Python**
- [`pyrtlsdr`](https://github.com/roger-/pyrtl-sdr) — RTL-SDR hardware interface
- **PyQt6** — GUI framework
- **PyQtGraph** — real-time plotting
- **NumPy** — FFT computation, windowing, signal processing
- **threading** — separate acquisition thread to keep the GUI responsive during continuous IQ streaming

You'll also need the RTL-SDR drivers installed on your system. See the [RTL-SDR Quick Start Guide](https://www.rtl-sdr.com/rtl-sdr-quick-start-guide/) for OS-specific setup instructions.

Once running:
1. Adjust the settings as desired
3. View live time-domain, amplitude-vs-frequency, PSD, and waterfall plots

## How It Works

The RTL-SDR streams raw IQ samples over USB, which are handled on a dedicated acquisition thread to avoid blocking the GUI. Each sample block is windowed and passed through an FFT (NumPy) to generate the frequency-domain views. The waterfall/spectrogram is built by stacking successive FFT outputs over time. FFT size is adjustable and interacts with the resolution bandwidth / video bandwidth settings, trading off frequency resolution against time resolution — the default is 2048 points.

## Acknowledgments

This project was informed by concepts from [*PySDR: A Guide to SDR and DSP using Python*](https://pysdr.org/) by Dr. Marc Lichtman — particularly the chapters on the Frequency Domain, IQ Sampling, RTL-SDR in Python, and Real-Time GUIs with PyQt.

## License

MIT
