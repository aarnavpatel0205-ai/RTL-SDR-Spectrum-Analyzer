from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QGridLayout, QVBoxLayout, QHBoxLayout, QSlider, QLabel, QComboBox, QStackedWidget, QLineEdit, QSizePolicy
from PyQt6.QtCore import QThread, QObject, pyqtSignal, QTimer, Qt, QRunnable, QThreadPool, pyqtSlot, QRectF, QPointF, QSizeF
from rtlsdr import RtlSdr
import numpy as np, pyqtgraph as pg, sys, threading

# SDR Initialization (RTL-SDR Blogv3) to Starting Settings
try:  # checks if the SDR is connected correctly
    sdr = RtlSdr()
except:
    print("Error, Connect the SDR to the laptop")
    sys.exit()
else:
    sdr.sample_rate = 1e6 #Hz
    sdr.center_freq = 100e6 #Hz
    sdr.freq_correction = 60  # PPM
    sdr.gain = 16.6  # dB

class SDRWorker1(QObject):
    def __init__(self):
        super().__init__()
        self._pause_event = threading.Event()
        self._lock = threading.Lock()  # Used to prevent RBWEdit from changing the fft_size while Main_Loop is using it
        self.num_rows = 200  # for waterfall
        self.RBW_val = 1000
        self.VBW_val = 50.0
        self.fft_size = int(sdr.sample_rate/self.RBW_val)
        self.time_plot_samples = 1000  # number of points shown on time plot
        self.WindowFunct = np.hamming(self.fft_size)
        self.WindowFunctIndex = 0
        self.num_frames = self.fft_size
        self.PSD_avg = np.ones(self.fft_size)
        self.FrequencySpectrumData = np.ones(self.fft_size)
        self.waterfall = np.ones((self.fft_size, self.num_rows))
        self.Beta_Val = 0.35
    
    EOR = pyqtSignal()
    Time_Plot_Update = pyqtSignal(np.ndarray)
    PSD_Plot_Update = pyqtSignal(np.ndarray)
    FreqSpectrumPlot_Update = pyqtSignal(np.ndarray)
    WaterFall_Update = pyqtSignal(np.ndarray)

    @pyqtSlot(float)
    def Set_VBW(self, VBW):
        self.VBW_val = VBW

    @pyqtSlot(float)
    def Set_Beta(self, Beta):
        self.Beta_Val = Beta

    @pyqtSlot(int)
    def Set_FFT_Size(self, FFT_Size):
        self.fft_size = FFT_Size
        self.PSD_avg = np.ones(self.fft_size)
        self.FrequencySpectrumData = np.ones(self.fft_size)
        self.waterfall = np.ones((self.fft_size, self.num_rows))

    def Main_Loop(self):
        self._pause_event.wait()  # .wait() forces a thread to wait until the event is set
        temp_size = self.fft_size
        def WindowFunct(index):
            match (index):
                case 0: return np.hamming(temp_size)
                case 1: return np.hanning(temp_size)
                case 2: return np.blackman(temp_size)
                case 3: return np.bartlett(temp_size)
                case 4: return np.kaiser(temp_size, self.Beta_Val)
                case 5: return 1 #rectangular window, (aka no window)
                case _: pass
        with self._lock:
            Samples = sdr.read_samples(temp_size)
            self.Time_Plot_Update.emit(Samples[0:self.time_plot_samples])

            self.WindowFunct = WindowFunct(self.WindowFunctIndex)
            Samples = Samples * self.WindowFunct  # Windowing
            self.FrequencySpectrumData = abs(np.fft.fftshift(np.fft.fft(Samples)))
            self.FreqSpectrumPlot_Update.emit(self.FrequencySpectrumData)

            PSD = 10 * np.log10(np.abs(np.fft.fftshift(np.fft.fft(Samples))) ** 2 / temp_size)
            self.PSD_avg = (1 - self.VBW_val / temp_size) * self.PSD_avg + (self.VBW_val / temp_size) * PSD
            self.PSD_Plot_Update.emit(self.PSD_avg)

            self.waterfall[:] = np.roll(self.waterfall, 1, axis=1)  # shifts waterfall 1 row
            self.waterfall[:, 0] = PSD  # Update last row with new fft results
            self.WaterFall_Update.emit(self.waterfall)

        self.EOR.emit()
    def pause(self):
        self._pause_event.clear()  # pause the thread
    def resume(self):
        self._pause_event.set()  # resume the thread

class SettingValidator(QObject):
    FFT_Signal = pyqtSignal(int)
    VBW_Signal = pyqtSignal(float)
    Beta_Signal = pyqtSignal(float)
    RBWMessage = pyqtSignal(str)
    FreqMessage = pyqtSignal(str)
    VBWMessage = pyqtSignal(str)
    BetaMessage = pyqtSignal(str)

    def NumsOnly(self,StringtoFilter):
        for i in StringtoFilter:
            if (i.isdigit() or i == '.'):
                continue
            return StringtoFilter[0:StringtoFilter.index(i)]
        return StringtoFilter  # if there is nothing to filter

    def __init__(self):
        super().__init__()
        self.RBW_val = 1000.0
        self.sample_rate = 1e6
        self.center_freq = sdr.center_freq
        self.VBW_val = 50.0
        self.Beta_val = 0.35
        self.FFT_size = int(sdr.sample_rate/self.RBW_val)
        self.Value = 0

    @pyqtSlot(str)
    def Get_Center_freq(self, center_freq):
        center_freq_num = self.NumsOnly(center_freq)
        if(len(center_freq_num) == 0):
            self.FreqMessage.emit("Invalid")
            return
        else:
            center_freq_num = float(center_freq_num)
        if (center_freq_num == (sdr.center_freq / 1e6)):
            self.FreqMessage.emit(f"{center_freq_num} MHz")
            return
        if (center_freq_num > 15.0):
            sdr.center_freq = center_freq_num * 1e6
            self.FreqMessage.emit(f"{center_freq_num} MHz")
            self.validate()
        else:
            self.FreqMessage.emit("Invalid")

    @pyqtSlot(str)
    def Get_RBW(self, RBW):
        RBW = self.NumsOnly(RBW)
        if(len(RBW) == 0):
            self.RBWMessage.emit("Invalid")
            return
        else:
            RBW = float(RBW)
        if (RBW == self.RBW_val):
            self.RBWMessage.emit(f"{RBW} Hz")
            return
        if (RBW < 5):
            self.RBWMessage.emit("Invalid")
            return
        self.RBW_val = RBW
        self.validate()
        self.RBWMessage.emit(f"{RBW} Hz")

    @pyqtSlot(str)
    def Get_VBW(self, VBW):
        VBW = self.NumsOnly(VBW)
        if(len(VBW) == 0):
            self.VBWMessage.emit("Invalid")
            return
        else:
            VBW = float(VBW)
        if (VBW == self.VBW_val):
            self.VBWMessage.emit(f"{VBW} Hz")
            return
        if (VBW <= 0.0 or VBW > self.RBW_val):
            self.VBWMessage.emit("Invalid")
            return
        self.VBW_val = VBW
        self.VBW_Signal.emit(VBW)
        self.VBWMessage.emit(f"{VBW} Hz")

    @pyqtSlot(str)
    def Get_Beta(self, Beta):
        Beta = self.NumsOnly(Beta)
        if(len(Beta) == 0):
            self.BetaMessage.emit("Invalid")
            return
        else:
            Beta = float(Beta)
        if(Beta == self.Beta_val):
            self.BetaMessage.emit(f"{Beta} Hz")
            return
        if(Beta < 0.0 or Beta > 1.0):
            self.BetaMessage.emit("Invalid")
            return
        self.Beta_val = Beta
        self.Beta_Signal.emit(Beta)
        self.BetaMessage.emit(f"{Beta} Hz")

    def validate(self):
        self.FFT_size = int(sdr.sample_rate/self.RBW_val)
        if (self.FFT_size > 3999000 or self.FFT_size < 5):  # size limits on FFT due to hardware
            self.VBWMessage.emit("Invalid")
        else:
            self.FFT_Signal.emit(self.FFT_size)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.sample_rates = [1e6, 1.25e6, 1.5e6, 1.75e6, 2e6, 2.048e6, 2.25e6, 2.4e6, 2.5e6, 2.75e6, 3e6, 3.2e6]  # Hz
        sdr.sample_rate = self.sample_rates[0] #1st element (1e6 Hz) as the starting value
        self.gains = [0.0, 0.9, 1.4, 2.7, 3.7, 7.7, 8.7, 12.5, 14.4, 15.7, 16.6, 19.7, 20.7, 22.9, 25.4, 28.0, 29.7,
                      32.8, 33.8, 36.4, 37.2, 38.6, 40.2, 42.1, 43.4, 43.9, 44.5, 48.0, 49.6]

        MainGUIWidget = QWidget()
        self.setCentralWidget(MainGUIWidget)
        MainGUILayout = QGridLayout()
        MainGUIWidget.setLayout(MainGUILayout)

        self.setWindowTitle("RTL-SDR Blog v3 Spectrum Analyzer App")
        self.resize(1000, 600)  # GUI Window size
        self.move(100, 100)  # Window Position

        # Worker and Thread Initialization
        self.validate_thread = QThread()
        self.ValidateWorker = SettingValidator()
        self.ValidateWorker.moveToThread(self.validate_thread)

        self.sdr_thread1 = QThread()
        SDR_Math_worker = SDRWorker1()
        SDR_Math_worker.moveToThread(self.sdr_thread1)

        self.ValidateWorker.FFT_Signal.connect(SDR_Math_worker.Set_FFT_Size)
        self.ValidateWorker.VBW_Signal.connect(SDR_Math_worker.Set_VBW)
        self.ValidateWorker.Beta_Signal.connect(SDR_Math_worker.Set_Beta)

        TimeIPlot = pg.PlotWidget()
        TimeIPlot.setYRange(-1, 1)
        TimeIPlot.setTitle('I Signal', size='12pt')
        TimeIPlot.setLabel('left', 'Amplitudes')
        TimeIPlot.setLabel('bottom', 'Time [ms]')
        TimeIPlot.showGrid(x=True, y=True)
        TimePlot_Icurve = TimeIPlot.plot([])

        TimeQPlot = pg.PlotWidget()
        TimeQPlot.setTitle('Q Signal', size='12pt')
        TimeQPlot.setLabel('left', 'Amplitudes')
        TimeQPlot.setLabel('bottom', 'Time [ms]')
        TimeQPlot.showGrid(x=True, y=True)
        TimeQPlot.setYRange(-1, 1)
        TimePlot_Qcurve = TimeQPlot.plot([])

        TimePlotWidget = QWidget()
        TimePlotLayout = QVBoxLayout()
        TimePlotLayout.addWidget(TimeIPlot)
        TimePlotLayout.addWidget(TimeQPlot)
        TimePlotWidget.setLayout(TimePlotLayout)

        PSD_Plot = pg.PlotWidget()
        PSD_Plot.setTitle('Power Spectral Density', size='12pt')
        PSD_Plot.setLabel('left', 'Power [dB]')
        PSD_Plot.setLabel('bottom', 'Frequency [Hz]')
        PSD_Plot.showGrid(x=True, y=True)
        PSD_Plot_Curve = PSD_Plot.plot([])
        PSD_Plot.setYRange(-50, 30)

        FrequencySpectrumPlot = pg.PlotWidget()
        FrequencySpectrumPlot.setTitle('Frequency Spectrum Plot', size='12pt')
        FrequencySpectrumPlot.setLabel('left', 'Amplitude')
        FrequencySpectrumPlot.setLabel('bottom', 'Frequency [Hz]')
        FrequencySpectrumPlot.setYRange(0, 300)
        FreqSpectrum_Curve = FrequencySpectrumPlot.plot([])

        WaterFallPlot = pg.PlotWidget()
        WaterFallPlot.setTitle('Waterfall', size='12pt')
        WaterFallPlot.setLabel('left', 'Time [s]')
        WaterFallPlot.setLabel('bottom', 'Frequency [Hz]')
        WaterFallImage = pg.ImageItem(axisOrder='col-major')
        WaterFallPlot.addItem(WaterFallImage)

        WaterFallColor = pg.HistogramLUTWidget()
        WaterFallColor.setImageItem(WaterFallImage)  # connects colorbar to spectrogram
        WaterFallColor.item.gradient.loadPreset('viridis')  # color mpa, sets the SpecImage
        WaterFallImage.setLevels((-40, 40))

        WaterFallWidget = QWidget()
        WaterFallLayout = QHBoxLayout()
        WaterFallWidget.setLayout(WaterFallLayout)
        WaterFallLayout.addWidget(WaterFallPlot)
        WaterFallLayout.addWidget(WaterFallColor)

        WidgetStack = QStackedWidget()
        WidgetStack.addWidget(TimePlotWidget)
        WidgetStack.addWidget(PSD_Plot)
        WidgetStack.addWidget(FrequencySpectrumPlot)
        WidgetStack.addWidget(WaterFallWidget)
        MainGUILayout.addWidget(WidgetStack, 0, 0)

        PlayButton = QPushButton("Play")
        def PlayButtonAction():
            SDR_Math_worker.resume()
        PlayButton.clicked.connect(PlayButtonAction)

        StopButton = QPushButton("Stop")
        def StopButtonAction():
            SDR_Math_worker.pause()
        StopButton.clicked.connect(StopButtonAction)

        GainComboBox = QComboBox()
        GainComboBox.addItems([f"{x} dB" for x in self.gains])
        GainComboBox.setCurrentIndex(self.gains.index(16.6))
        GainLabel = QLabel()
        GainLabel.setText("Gain: ")
        def UpdateGain(val):
            SDR_Math_worker.pause()
            sdr.gain = self.gains[val]
            SDR_Math_worker.resume()
        GainComboBox.currentIndexChanged.connect(lambda : UpdateGain(GainComboBox.currentIndex()))

        # Sampling Rate (SR) Selection Drop Down, Span Control
        SpanComboBox = QComboBox()
        SpanComboBox.addItems([f"{x/1e6} MHz" for x in self.sample_rates])
        SpanComboBox.setCurrentIndex(0)  # make sure it matches the starting value (self.sample_rate = 1e6)
        SpanLabel = QLabel()
        SpanLabel.setText("Span: ")
        def UpdateSR(val):
            SDR_Math_worker.pause()
            sdr.sample_rate = self.sample_rates[val]
            PSD_Plot.setXRange((sdr.center_freq - sdr.sample_rate / 2), (sdr.center_freq + sdr.sample_rate / 2))  # Units in Hz
            SDR_Math_worker.resume()
        SpanComboBox.currentIndexChanged.connect(lambda: UpdateSR(SpanComboBox.currentIndex()))

        CenterFrequencyLabel = QLabel()
        CenterFrequencyEdit = QLineEdit(f"{sdr.center_freq/1e6} MHz")
        CenterFrequencyLabel.setText("Center\nFrequency:")
        def CenterFreqVal():
            SDR_Math_worker.pause()
            self.ValidateWorker.Get_Center_freq(CenterFrequencyEdit.text())
            SDR_Math_worker.resume()
        CenterFrequencyEdit.editingFinished.connect(CenterFreqVal)

        @pyqtSlot(str)
        def CenterFreqLabel_Update(CenterFreq_Message):
            CenterFrequencyEdit.setText(CenterFreq_Message)
        self.ValidateWorker.FreqMessage.connect(CenterFreqLabel_Update)

        TimePlotAuto = QPushButton("Time Plot\nAuto Range")
        def TimeAutoRange():
            TimeIPlot.autoRange()
            TimeQPlot.autoRange()
        TimePlotAuto.clicked.connect(TimeAutoRange)
        PSD_PlotAuto = QPushButton("PSD \nAuto Range")
        PSD_PlotAuto.clicked.connect(lambda: PSD_Plot.autoRange())

        FrequencyCorrectLabel = QLabel()
        FrequencyCorrectLabel.setText(f"Frequency\nCorrection: {sdr.freq_correction} PPM")
        FrequencyCorrect = QSlider(Qt.Orientation.Horizontal)
        FrequencyCorrect.setRange(0, 200)  # figure out the max and min values, blog will not accept values less than 0
        FrequencyCorrect.setTickInterval(1)
        FrequencyCorrect.setValue(60)
        def FreqCorrectUpdate(val):
            SDR_Math_worker.pause()
            sdr.freq_correction = val
            SDR_Math_worker.resume()
        FrequencyCorrect.sliderMoved.connect(lambda: FrequencyCorrectLabel.setText(f"Frequency Correction: {FrequencyCorrect.value()} PPM"))
        FrequencyCorrect.sliderReleased.connect(lambda: FreqCorrectUpdate(FrequencyCorrect.value()))

        # Resolution Bandwith (RBW) control
        RBWLabel = QLabel()
        RBWLabel.setText("RBW: ")
        RBWEdit = QLineEdit(f"{SDR_Math_worker.RBW_val} Hz")
        def RBW_Update():
            SDR_Math_worker.pause()
            self.ValidateWorker.Get_RBW(RBWEdit.text())
            SDR_Math_worker.resume()
        RBWEdit.editingFinished.connect(RBW_Update)

        @pyqtSlot(str)
        def RBW_Edit_Update(RBW_Message):
            RBWEdit.setText(RBW_Message)
        self.ValidateWorker.RBWMessage.connect(RBW_Edit_Update)

        # Video BandWidth (VBW) control
        VBWLabel = QLabel()
        VBWLabel.setText("VBW: ")
        VBWEdit = QLineEdit()
        VBWEdit.setText(f"{SDR_Math_worker.VBW_val} Hz")
        def VBW_Update():
            SDR_Math_worker.pause()
            self.ValidateWorker.Get_VBW(VBWEdit.text())
            SDR_Math_worker.resume()
        VBWEdit.editingFinished.connect(VBW_Update)

        @pyqtSlot(str)
        def VBW_Edit_Update(VBW_Message):
            VBWEdit.setText(VBW_Message)
        self.ValidateWorker.VBWMessage.connect(VBW_Edit_Update)

        WindowFunctSelection = QComboBox()
        WindowFunctSelection.addItems(['Hamming', 'Hanning', 'Blackman', 'Bartlett', 'Kaiser', 'Rectangular'])
        WindowFunctSelection.setCurrentIndex(0)
        WindowFunctLabel = QLabel()
        WindowFunctLabel.setText("Window Function")
        def WindowFunctUpdate():
            SDR_Math_worker.pause()
            SDR_Math_worker.WindowFunctIndex = WindowFunctSelection.currentIndex()
            SDR_Math_worker.resume()
        WindowFunctSelection.currentIndexChanged.connect(WindowFunctUpdate)

        BetaLabel = QLabel()
        BetaLabel.setText("Beta: ")
        BetaEdit = QLineEdit(f"{SDR_Math_worker.Beta_Val}")
        def Beta_Update():
            self.ValidateWorker.Get_Beta(BetaEdit.text())
        BetaEdit.editingFinished.connect(Beta_Update)

        @pyqtSlot(str)
        def Beta_Edit_Update(Beta_Message):
            BetaEdit.setText(Beta_Message)
        self.ValidateWorker.BetaMessage.connect(Beta_Edit_Update)

        #Cursors
        CursorDisplayWidget = QWidget()
        CursorDisplayWidget.setFixedHeight(150)
        CursorWidgetStack1 = QStackedWidget()
        CursorWidgetStack2 = QStackedWidget()
        CursorDisplayLabel = QLabel()
        CursorDisplayLabel.setText("Cursors")

        def MakeCursor(AngleVal, position):
            CursorLabelOptions = {'movable': True, 'color': 'black', 'fill' : 'white', 'position' : 0.75}  # For the cursors placed on the plot(s)
            Cursor = pg.InfiniteLine(pen=pg.mkPen('#ff0000', width=3), label="", angle=AngleVal, pos=position, labelOpts=CursorLabelOptions, movable=True)  # 0 is a starting position
            Cursor.label.setText(f"{Cursor.value():.4f}")
            def CursorValueUpdate():
                Cursor.label.setText(f"{Cursor.value():.4f}")  # updates the cursor label, val is truncated to 4 decimal places
            Cursor.sigPositionChanged.connect(CursorValueUpdate)
            return Cursor

        TimeCursorButton = QPushButton("Time") #One TimeCursorButton per CursorStack, both function similarly
        TimeCursorButton2 = QPushButton("Time")
        def AddTimeCursor():
            match WidgetStack.currentIndex():
                case 0: #Time Plot
                    IPlotCursor = MakeCursor(90, 500)
                    TimeIPlot.addItem(IPlotCursor)
                    QPlotCursor = MakeCursor(90, 500)
                    TimeQPlot.addItem(QPlotCursor)
                case 2: #Frequency Spectrum Plot
                    FrequencySpectrumCursor = MakeCursor(0, 0.5)
                    FrequencySpectrumPlot.addItem(FrequencySpectrumCursor)
                case 3: #WaterFall Plot
                    WaterFallCursor = MakeCursor(0, 100)
                    WaterFallPlot.addItem(WaterFallCursor)
        TimeCursorButton.clicked.connect(AddTimeCursor)
        TimeCursorButton2.clicked.connect(AddTimeCursor)

        FrequencyCursorButton = QPushButton("Frequency")
        def AddFrequencyCursor():
            match WidgetStack.currentIndex():
                case 1:  # Power Spectral Density Plot
                    FrequencyCursor = MakeCursor(90, sdr.center_freq)
                    PSD_Plot.addItem(FrequencyCursor)
                case 2:  # Frequency Spectrum Plot
                    FreqSpectrumCursor = MakeCursor(90, sdr.center_freq)
                    FrequencySpectrumPlot.addItem(FreqSpectrumCursor)
                case 3:  # WaterFall Plot
                    WaterFallCursor = MakeCursor(90, 1000)
                    WaterFallPlot.addItem(WaterFallCursor)
                case _:
                    pass
        FrequencyCursorButton.clicked.connect(AddFrequencyCursor)

        PowerCursorButton = QPushButton("Power")
        def AddPowerCursor():
            FrequencyCursor = MakeCursor(0, 0)
            PSD_Plot.addItem(FrequencyCursor)
        PowerCursorButton.clicked.connect(AddPowerCursor)

        AmplitudeCursorButton = QPushButton("Amplitude")
        def AddAmplitudeCursor():
            match WidgetStack.currentIndex():
                case 0:
                    IPlotCursor = MakeCursor( 0, 0.25)
                    TimeIPlot.addItem(IPlotCursor)
                    QPlotCursor = MakeCursor( 0, 0.25)
                    TimeQPlot.addItem(QPlotCursor)
                case 2:
                    FreqSpectrumCursor = MakeCursor(0, 200)
                    FrequencySpectrumPlot.addItem(FreqSpectrumCursor)
        AmplitudeCursorButton.clicked.connect(AddAmplitudeCursor)

        RemoveAllCursorsButton = QPushButton("Remove Cursors")
        def CursorRemove(CurrentWidget):
            for item in CurrentWidget.items():
                if isinstance(item, pg.InfiniteLine):
                    CurrentWidget.removeItem(item)
        def CursorFind():
            match (WidgetStack.currentIndex()):
                case 0:
                    CursorRemove(TimeIPlot)
                    CursorRemove(TimeQPlot)
                case 1:
                    CursorRemove(PSD_Plot)
                case 2:
                    CursorRemove(FrequencySpectrumPlot)
                case 3:
                    CursorRemove(WaterFallPlot)
                case _:
                    print("No Plot Detected")  # something is really wrong if this appears on the console
        RemoveAllCursorsButton.clicked.connect(CursorFind)

        CursorDisplayLayout = QVBoxLayout()
        CursorDisplayWidget.setLayout(CursorDisplayLayout)
        CursorDisplayLayout.addWidget(CursorDisplayLabel)

        CursorWidgetStack1.addWidget(TimeCursorButton)
        CursorWidgetStack1.addWidget(FrequencyCursorButton)

        CursorWidgetStack2.addWidget(AmplitudeCursorButton)
        CursorWidgetStack2.addWidget(PowerCursorButton)
        CursorWidgetStack2.addWidget(TimeCursorButton2)

        CursorDisplayLayout.addWidget(CursorWidgetStack1)
        CursorDisplayLayout.addWidget(CursorWidgetStack2)
        CursorDisplayLayout.addWidget(RemoveAllCursorsButton)

        BetaLayout = QHBoxLayout()
        BetaLayout.addWidget(BetaLabel)
        BetaLayout.addWidget(BetaEdit)

        WindowFunctWidget = QWidget()
        WindowFunctLayout = QVBoxLayout()
        WindowFunctWidget.setLayout(WindowFunctLayout)
        WindowFunctLayout.addWidget(WindowFunctLabel)
        WindowFunctLayout.addWidget(WindowFunctSelection)
        WindowFunctLayout.addLayout(BetaLayout)

        AdditionalFeaturesNotice = QLabel()
        AdditionalFeaturesNotice.setText("Right Click Plots for more options!\n"
                                         "To edit RBW, click stop first\n"
                                         "You can drag and click the cursor values")

        ButtonControlLayout = QGridLayout()
        ButtonControlLayout.addWidget(PlayButton, 0, 0)
        ButtonControlLayout.addWidget(StopButton, 0, 1)
        ButtonControlLayout.addWidget(TimePlotAuto, 1, 0)
        ButtonControlLayout.addWidget(PSD_PlotAuto, 1, 1)

        SDRSettingsLayout = QGridLayout()
        SDRSettingsLayout.addWidget(GainLabel, 0, 0)
        SDRSettingsLayout.addWidget(GainComboBox, 0, 1)
        SDRSettingsLayout.addWidget(SpanLabel, 1, 0)
        SDRSettingsLayout.addWidget(SpanComboBox, 1, 1)
        SDRSettingsLayout.addWidget(CenterFrequencyLabel, 2, 0)
        SDRSettingsLayout.addWidget(CenterFrequencyEdit, 2, 1)
        SDRSettingsLayout.addWidget(RBWLabel, 3, 0)
        SDRSettingsLayout.addWidget(RBWEdit, 3, 1)
        SDRSettingsLayout.addWidget(VBWLabel, 4, 0)
        SDRSettingsLayout.addWidget(VBWEdit, 4, 1)

        ControlLayout = QGridLayout()
        ControlLayout.addLayout(ButtonControlLayout, 0, 0)
        ControlLayout.addLayout(SDRSettingsLayout, 1, 0)
        ControlLayout.addWidget(FrequencyCorrectLabel, 2, 0)
        ControlLayout.addWidget(FrequencyCorrect, 3, 0)
        ControlLayout.addWidget(CursorDisplayWidget, 4, 0)
        ControlLayout.addWidget(WindowFunctWidget, 5, 0)
        ControlLayout.addWidget(AdditionalFeaturesNotice, 6, 0)
        MainGUILayout.addLayout(ControlLayout, 0, 1)

        # Buttons (for determining which plot and cursors to display)
        TimePlotButton = QPushButton("Time Plot")
        def TimePlotSet():
            WidgetStack.setCurrentWidget(TimePlotWidget)
            CursorWidgetStack1.setCurrentWidget(TimeCursorButton)
            CursorWidgetStack2.setCurrentWidget(AmplitudeCursorButton)
        TimePlotButton.clicked.connect(TimePlotSet)

        PSD_PlotButton = QPushButton("Power Spectrum Density Plot")
        def PSD_PlotSet():
            WidgetStack.setCurrentWidget(PSD_Plot)
            CursorWidgetStack1.setCurrentWidget(FrequencyCursorButton)
            CursorWidgetStack2.setCurrentWidget(PowerCursorButton)
        PSD_PlotButton.clicked.connect(PSD_PlotSet)

        FrequencySpectrumPlotButton = QPushButton("Frequency Spectrum Plot")
        def FrequencySpectrumPlotSet():
            WidgetStack.setCurrentWidget(FrequencySpectrumPlot)
            CursorWidgetStack1.setCurrentWidget(FrequencyCursorButton)
            CursorWidgetStack2.setCurrentWidget(AmplitudeCursorButton)
        FrequencySpectrumPlotButton.clicked.connect(FrequencySpectrumPlotSet)

        WaterFallButton = QPushButton("Waterfall")
        def WaterFallPlotSet():
            WidgetStack.setCurrentWidget(WaterFallWidget)
            CursorWidgetStack1.setCurrentWidget(FrequencyCursorButton)
            CursorWidgetStack2.setCurrentWidget(TimeCursorButton2)
        WaterFallButton.clicked.connect(WaterFallPlotSet)

        ButtonLayout = QHBoxLayout()
        ButtonLayout.addWidget(TimePlotButton)
        ButtonLayout.addWidget(PSD_PlotButton)
        ButtonLayout.addWidget(FrequencySpectrumPlotButton)
        ButtonLayout.addWidget(WaterFallButton)
        MainGUILayout.addLayout(ButtonLayout, 1, 0)

        # Signals and Slots (and some plot customization)
        def TimePlot_Callback(samples):
            TimePlot_Icurve.setData(samples.real, pen=pg.mkPen(color='c'))
            TimePlot_Qcurve.setData(samples.imag, pen=pg.mkPen(color=(255, 165, 0)))  # orange color
        def PSD_Plot_Callback(PSD):
            try:
                Frequency_axis = np.linspace(sdr.center_freq - sdr.sample_rate / 2, sdr.center_freq + sdr.sample_rate / 2, SDR_Math_worker.fft_size)
                PSD_Plot_Curve.setData(Frequency_axis, PSD)
            except:
                print("Sizing error, trying again...")
        def FrequencySpectrum_Callback(PlotData):
            try:
                Frequency_axis = np.linspace(sdr.center_freq - sdr.sample_rate / 2, sdr.center_freq + sdr.sample_rate / 2, SDR_Math_worker.fft_size)
                FreqSpectrum_Curve.setData(Frequency_axis, PlotData)
            except:
                print("Sizing error2, trying again...")
        def WaterFall_CallBack(waterfall):
            WaterFallImage.setImage(waterfall, autolevels=True)
            WaterFallImage.setRect(QRectF(sdr.center_freq - sdr.sample_rate/2, 0, sdr.sample_rate, SDR_Math_worker.num_rows))

        SDR_Math_worker.Time_Plot_Update.connect(TimePlot_Callback)
        SDR_Math_worker.PSD_Plot_Update.connect(PSD_Plot_Callback)
        SDR_Math_worker.FreqSpectrumPlot_Update.connect(FrequencySpectrum_Callback)
        SDR_Math_worker.WaterFall_Update.connect(WaterFall_CallBack)
        SDR_Math_worker.EOR.connect(lambda: QTimer.singleShot(0, SDR_Math_worker.Main_Loop))

        self.validate_thread.start()
        self.sdr_thread1.started.connect(SDR_Math_worker.Main_Loop)
        self.sdr_thread1.start()

app = QApplication([])
window = MainWindow() #creates a window
window.show()
app.exec()  # starts the event loop
sdr.close()  # closes SDR once the GUI is closed
