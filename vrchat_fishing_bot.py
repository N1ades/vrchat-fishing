import time
import threading
import ctypes
import ctypes.wintypes
import numpy as np
import pyaudio
import tkinter as tk
from tkinter import ttk, messagebox
import win32gui
import win32con
import win32api
import win32process
import queue
import logging
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
import struct
import json
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Путь к файлу настроек
SETTINGS_FILE = "fishing_bot_settings.json"

class VRChatFishingBot:
    def __init__(self):
        self.running = False
        self.paused = False
        self.vrchat_window = None
        self.vrchat_process_id = None
        self.vrchat_audio_session = None
        self.audio_thread = None
        self.bot_thread = None
        self.audio_queue = queue.Queue()
        
        # Настройки для рыбалки (значения по умолчанию)
        self.cast_duration = 0.5  # Время зажатия E для заброса (секунды)
        self.min_reel_time = 5.0  # Минимальное время перед началом прослушивания музыки (секунды)
        self.audio_threshold = 0.05  # Порог громкости для детекции звука клева
        self.music_threshold = 0.01  # Порог громкости для музыки подсечки
        self.additional_wait = 1.5  # Дополнительное время после окончания музыки (секунды)
        self.cooldown_after_cast = 5.0  # Время игнорирования звуков после заброса (секунды)
        self.spike_cooldown = 0.5  # Минимальный интервал между обнаружениями звуков (секунды)
        self.smoothing_alpha = 0.3  # Коэффициент сглаживания аудио (0.1-0.9)
        
        # Загружаем настройки из файла
        self.load_settings()
        
        self.sample_rate = 44100
        self.chunk_size = 1024
        
        # Windows API константы
        self.VK_E = 0x45
        self.KEYEVENTF_KEYUP = 0x0002
        
        # Инициализация GUI
        self.setup_gui()
        
    def setup_gui(self):
        """Создание графического интерфейса"""
        self.root = tk.Tk()
        self.root.title("VRChat Fishing Bot")
        self.root.geometry("540x700")
        self.root.resizable(False, False)
        
        # Главный фрейм
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Заголовок
        title_label = ttk.Label(main_frame, text="VRChat Fishing Bot", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Настройки
        settings_frame = ttk.LabelFrame(main_frame, text="Настройки", padding="10")
        settings_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Время заброса
        ttk.Label(settings_frame, text="Время заброса (сек):").grid(row=0, column=0, sticky=tk.W)
        self.cast_duration_var = tk.DoubleVar(value=self.cast_duration)
        cast_spinbox = ttk.Spinbox(settings_frame, from_=0.1, to=2.0, increment=0.1, 
                                  textvariable=self.cast_duration_var, width=10)
        cast_spinbox.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        
        # Минимальное время подсечки
        ttk.Label(settings_frame, text="Мин. время до музыки (сек):").grid(row=1, column=0, sticky=tk.W)
        self.min_reel_time_var = tk.DoubleVar(value=self.min_reel_time)
        reel_spinbox = ttk.Spinbox(settings_frame, from_=5.0, to=30.0, increment=1.0, 
                                  textvariable=self.min_reel_time_var, width=10)
        reel_spinbox.grid(row=1, column=1, sticky=tk.W, padx=(10, 0))
        
        # Порог громкости для клева
        ttk.Label(settings_frame, text="Порог клева:").grid(row=2, column=0, sticky=tk.W)
        self.audio_threshold_var = tk.DoubleVar(value=self.audio_threshold)
        threshold_spinbox = ttk.Spinbox(settings_frame, from_=0.01, to=1.0, increment=0.01, 
                                       textvariable=self.audio_threshold_var, width=10,
                                       command=self.on_threshold_changed)
        threshold_spinbox.grid(row=2, column=1, sticky=tk.W, padx=(10, 0))
        
        # Порог громкости для музыки
        ttk.Label(settings_frame, text="Порог музыки:").grid(row=3, column=0, sticky=tk.W)
        self.music_threshold_var = tk.DoubleVar(value=self.music_threshold)
        music_spinbox = ttk.Spinbox(settings_frame, from_=0.01, to=1.0, increment=0.01, 
                                   textvariable=self.music_threshold_var, width=10)
        music_spinbox.grid(row=3, column=1, sticky=tk.W, padx=(10, 0))
        
        # Дополнительное время после музыки
        ttk.Label(settings_frame, text="Доп. время после музыки (сек):").grid(row=4, column=0, sticky=tk.W)
        self.additional_wait_var = tk.DoubleVar(value=self.additional_wait)
        wait_spinbox = ttk.Spinbox(settings_frame, from_=1.0, to=15.0, increment=0.5, 
                                  textvariable=self.additional_wait_var, width=10)
        wait_spinbox.grid(row=4, column=1, sticky=tk.W, padx=(10, 0))
        
        # Пауза после заброса
        ttk.Label(settings_frame, text="Пауза после заброса (сек):").grid(row=5, column=0, sticky=tk.W)
        self.cooldown_after_cast_var = tk.DoubleVar(value=self.cooldown_after_cast)
        cooldown_spinbox = ttk.Spinbox(settings_frame, from_=0.0, to=15.0, increment=0.5, 
                                      textvariable=self.cooldown_after_cast_var, width=10)
        cooldown_spinbox.grid(row=5, column=1, sticky=tk.W, padx=(10, 0))
        
        # Интервал между звуками
        ttk.Label(settings_frame, text="Интервал между звуками (сек):").grid(row=6, column=0, sticky=tk.W)
        self.spike_cooldown_var = tk.DoubleVar(value=self.spike_cooldown)
        spike_spinbox = ttk.Spinbox(settings_frame, from_=0.1, to=2.0, increment=0.1, 
                                   textvariable=self.spike_cooldown_var, width=10)
        spike_spinbox.grid(row=6, column=1, sticky=tk.W, padx=(10, 0))
        
        # Сглаживание аудио
        ttk.Label(settings_frame, text="Сглаживание аудио (0.1-0.9):").grid(row=7, column=0, sticky=tk.W)
        self.smoothing_alpha_var = tk.DoubleVar(value=self.smoothing_alpha)
        smooth_spinbox = ttk.Spinbox(settings_frame, from_=0.1, to=0.9, increment=0.1, 
                                    textvariable=self.smoothing_alpha_var, width=10)
        smooth_spinbox.grid(row=7, column=1, sticky=tk.W, padx=(10, 0))
        
        # Привязываем событие изменения
        self.audio_threshold_var.trace_add('write', lambda *args: self.on_threshold_changed())
        
        # Кнопки управления
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        self.start_button = ttk.Button(control_frame, text="Запустить бота", 
                                      command=self.start_bot, style="Accent.TButton")
        self.start_button.grid(row=0, column=0, padx=(0, 5))
        
        self.stop_button = ttk.Button(control_frame, text="Остановить бота", 
                                     command=self.stop_bot, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=(5, 5))
        
        self.save_button = ttk.Button(control_frame, text="Сохранить настройки", 
                                     command=self.save_settings_from_gui)
        self.save_button.grid(row=0, column=2, padx=(5, 0))
        
        # Статус
        self.status_var = tk.StringVar(value="Готов к запуску")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, 
                                font=("Arial", 10, "italic"))
        status_label.grid(row=3, column=0, columnspan=2, pady=10)
        
        # Визуализация громкости
        volume_frame = ttk.LabelFrame(main_frame, text="Мониторинг звука", padding="10")
        volume_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # Метка текущей громкости
        volume_info_frame = ttk.Frame(volume_frame)
        volume_info_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Label(volume_info_frame, text="Текущая громкость:").grid(row=0, column=0, sticky=tk.W)
        self.current_volume_label = ttk.Label(volume_info_frame, text="0.000", 
                                             font=("Arial", 10, "bold"), foreground="blue")
        self.current_volume_label.grid(row=0, column=1, sticky=tk.W, padx=(10, 20))
        
        ttk.Label(volume_info_frame, text="Порог:").grid(row=0, column=2, sticky=tk.W)
        self.threshold_label = ttk.Label(volume_info_frame, text="0.150", 
                                        font=("Arial", 10, "bold"), foreground="red")
        self.threshold_label.grid(row=0, column=3, sticky=tk.W, padx=(10, 0))
        
        # Canvas для визуализации
        self.volume_canvas = tk.Canvas(volume_frame, height=60, bg="white", highlightthickness=1, 
                                      highlightbackground="gray")
        self.volume_canvas.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Метка статуса обнаружения
        self.detection_label = ttk.Label(volume_frame, text="● Ожидание звука...", 
                                        font=("Arial", 9), foreground="gray")
        self.detection_label.grid(row=2, column=0, columnspan=2, pady=(5, 0))
        
        # Лог
        log_frame = ttk.LabelFrame(main_frame, text="Лог активности", padding="5")
        log_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        
        self.log_text = tk.Text(log_frame, height=6, width=50, state="disabled")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Настройка весов для растягивания
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(5, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        volume_frame.columnconfigure(0, weight=1)
        
        # Переменные для визуализации
        self.volume_history = []
        self.max_history = 100  # Храним последние 100 значений
    
    def load_settings(self):
        """Загрузка настроек из файла"""
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    
                self.cast_duration = settings.get('cast_duration', self.cast_duration)
                self.min_reel_time = settings.get('min_reel_time', self.min_reel_time)
                self.audio_threshold = settings.get('audio_threshold', self.audio_threshold)
                self.music_threshold = settings.get('music_threshold', self.music_threshold)
                self.additional_wait = settings.get('additional_wait', self.additional_wait)
                self.cooldown_after_cast = settings.get('cooldown_after_cast', self.cooldown_after_cast)
                self.spike_cooldown = settings.get('spike_cooldown', self.spike_cooldown)
                self.smoothing_alpha = settings.get('smoothing_alpha', self.smoothing_alpha)
                
                logger.info(f"Настройки загружены из {SETTINGS_FILE}")
        except Exception as e:
            logger.warning(f"Не удалось загрузить настройки: {e}")
    
    def save_settings(self):
        """Сохранение настроек в файл"""
        try:
            settings = {
                'cast_duration': self.cast_duration,
                'min_reel_time': self.min_reel_time,
                'audio_threshold': self.audio_threshold,
                'music_threshold': self.music_threshold,
                'additional_wait': self.additional_wait,
                'cooldown_after_cast': self.cooldown_after_cast,
                'spike_cooldown': self.spike_cooldown,
                'smoothing_alpha': self.smoothing_alpha
            }
            
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
                
            logger.info(f"Настройки сохранены в {SETTINGS_FILE}")
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек: {e}")
        
    def log_message(self, message):
        """Добавление сообщения в лог"""
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        logger.info(message)
    
    def on_threshold_changed(self):
        """Обработка изменения порога громкости"""
        try:
            self.audio_threshold = self.audio_threshold_var.get()
            self.threshold_label.config(text=f"{self.audio_threshold:.3f}")
        except Exception as e:
            pass  # Игнорируем ошибки при инициализации
    
    def save_settings_from_gui(self):
        """Сохранение настроек из GUI"""
        try:
            # Обновляем все настройки из GUI
            self.cast_duration = self.cast_duration_var.get()
            self.min_reel_time = self.min_reel_time_var.get()
            self.audio_threshold = self.audio_threshold_var.get()
            self.music_threshold = self.music_threshold_var.get()
            self.additional_wait = self.additional_wait_var.get()
            self.cooldown_after_cast = self.cooldown_after_cast_var.get()
            self.spike_cooldown = self.spike_cooldown_var.get()
            self.smoothing_alpha = self.smoothing_alpha_var.get()
            
            # Сохраняем в файл
            self.save_settings()
            
            self.log_message("Настройки сохранены!")
            messagebox.showinfo("Успех", "Настройки успешно сохранены!")
        except Exception as e:
            self.log_message(f"Ошибка сохранения настроек: {e}")
            messagebox.showerror("Ошибка", f"Не удалось сохранить настройки: {e}")
    
    def update_volume_visualization(self, volume):
        """Обновление визуализации громкости"""
        try:
            # Обновляем метку текущей громкости
            self.current_volume_label.config(text=f"{volume:.3f}")
            
            # Обновляем метку порога
            self.threshold_label.config(text=f"{self.audio_threshold:.3f}")
            
            # Добавляем значение в историю
            self.volume_history.append(volume)
            if len(self.volume_history) > self.max_history:
                self.volume_history.pop(0)
            
            # Очищаем canvas
            self.volume_canvas.delete("all")
            
            canvas_width = self.volume_canvas.winfo_width()
            canvas_height = self.volume_canvas.winfo_height()
            
            if canvas_width <= 1:  # Canvas еще не отрисован
                canvas_width = 480
            if canvas_height <= 1:
                canvas_height = 60
            
            # Рисуем сетку
            for i in range(0, 11):
                y = canvas_height - (i * canvas_height / 10)
                self.volume_canvas.create_line(0, y, canvas_width, y, 
                                              fill="#e0e0e0", width=1)
            
            # Рисуем линию порога
            threshold_y = canvas_height - (self.audio_threshold * canvas_height)
            self.volume_canvas.create_line(0, threshold_y, canvas_width, threshold_y, 
                                          fill="red", width=2, dash=(5, 3))
            self.volume_canvas.create_text(canvas_width - 5, threshold_y - 10, 
                                          text=f"Порог: {self.audio_threshold:.2f}", 
                                          anchor="e", fill="red", font=("Arial", 8))
            
            # Рисуем график громкости
            if len(self.volume_history) > 1:
                points = []
                for i, vol in enumerate(self.volume_history):
                    x = (i / max(len(self.volume_history) - 1, 1)) * canvas_width
                    y = canvas_height - (min(vol, 1.0) * canvas_height)
                    points.append((x, y))
                
                # Рисуем линию графика
                for i in range(len(points) - 1):
                    x1, y1 = points[i]
                    x2, y2 = points[i + 1]
                    
                    # Цвет зависит от того, превышает ли порог
                    if self.volume_history[i] > self.audio_threshold:
                        color = "#00cc00"  # Зеленый, если выше порога
                        width = 2
                    else:
                        color = "#3366ff"  # Синий, если ниже
                        width = 1
                    
                    self.volume_canvas.create_line(x1, y1, x2, y2, 
                                                  fill=color, width=width, smooth=True)
            
            # Рисуем текущее значение
            current_y = canvas_height - (min(volume, 1.0) * canvas_height)
            self.volume_canvas.create_oval(canvas_width - 8, current_y - 4, 
                                          canvas_width - 2, current_y + 4, 
                                          fill="blue", outline="darkblue", width=2)
            
            # Обновляем статус обнаружения
            if volume > self.audio_threshold:
                self.detection_label.config(text="● ЗВУК ОБНАРУЖЕН!", foreground="green")
                self.current_volume_label.config(foreground="green")
            else:
                self.detection_label.config(text="● Ожидание звука...", foreground="gray")
                self.current_volume_label.config(foreground="blue")
                
        except Exception as e:
            logger.error(f"Ошибка визуализации: {e}")
        
    def find_vrchat_window(self):
        """Поиск окна VRChat"""
        try:
            # Попробуем найти окно VRChat по заголовку
            hwnd = win32gui.FindWindow(None, "VRChat")
            if hwnd == 0:
                # Если не найдено, попробуем найти по частичному совпадению
                def enum_windows_callback(hwnd, results):
                    window_text = win32gui.GetWindowText(hwnd)
                    if "vrchat" in window_text.lower():
                        results.append(hwnd)
                
                results = []
                win32gui.EnumWindows(enum_windows_callback, results)
                
                if results:
                    hwnd = results[0]
                else:
                    return None
            
            self.vrchat_window = hwnd
            
            # Получаем ID процесса VRChat
            _, process_id = win32process.GetWindowThreadProcessId(hwnd)
            self.vrchat_process_id = process_id
            
            self.log_message(f"Найдено окно VRChat: {win32gui.GetWindowText(hwnd)} (PID: {process_id})")
            
            # Ищем аудио сессию VRChat
            self.find_vrchat_audio_session()
            
            return hwnd
            
        except Exception as e:
            self.log_message(f"Ошибка поиска окна VRChat: {e}")
            return None
    
    def find_vrchat_audio_session(self):
        """Поиск аудио сессии VRChat"""
        try:
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if session.Process and session.Process.pid == self.vrchat_process_id:
                    self.vrchat_audio_session = session
                    self.log_message(f"Найдена аудио сессия VRChat: {session.Process.name()}")
                    return True
            
            self.log_message("Аудио сессия VRChat не найдена")
            return False
            
        except Exception as e:
            self.log_message(f"Ошибка поиска аудио сессии: {e}")
            return False
    
    def activate_vrchat_window(self):
        """Активация окна VRChat"""
        if not self.vrchat_window:
            if not self.find_vrchat_window():
                return False
        
        try:
            # Проверяем, существует ли еще окно
            if not win32gui.IsWindow(self.vrchat_window):
                self.vrchat_window = None
                if not self.find_vrchat_window():
                    return False
            
            # Активируем окно
            win32gui.SetForegroundWindow(self.vrchat_window)
            time.sleep(0.1)  # Небольшая задержка для активации
            return True
            
        except Exception as e:
            self.log_message(f"Ошибка активации окна VRChat: {e}")
            return False
    
    def press_key(self, vk_code, duration=None):
        """Нажатие клавиши с опциональным удержанием"""
        try:
            if not self.activate_vrchat_window():
                self.log_message("Не удалось активировать окно VRChat")
                return False
            
            # Нажимаем клавишу
            win32api.keybd_event(vk_code, 0, 0, 0)
            
            if duration:
                # Удерживаем клавишу указанное время
                time.sleep(duration)
                # Отпускаем клавишу
                win32api.keybd_event(vk_code, 0, self.KEYEVENTF_KEYUP, 0)
            else:
                # Сразу отпускаем
                win32api.keybd_event(vk_code, 0, self.KEYEVENTF_KEYUP, 0)
            
            return True
            
        except Exception as e:
            self.log_message(f"Ошибка нажатия клавиши: {e}")
            return False
    
    def cast_fishing_line(self):
        """Заброс удочки"""
        self.log_message("Закидываю удочку...")
        self.status_var.set("Закидываю удочку...")
        
        success = self.press_key(self.VK_E, self.cast_duration)
        if success:
            self.log_message(f"Удочка заброшена (удержание {self.cast_duration}с)")
        else:
            self.log_message("Ошибка при забросе удочки")
        
        return success
    
    def start_audio_monitoring(self):
        """Запуск мониторинга аудио из окна VRChat"""
        try:
            if not self.vrchat_audio_session:
                self.log_message("Аудио сессия VRChat не найдена!")
                return
            
            # Получаем интерфейс для измерения громкости
            volume_interface = self.vrchat_audio_session._ctl.QueryInterface(IAudioMeterInformation)
            
            self.log_message("Запущен мониторинг аудио из VRChat")
            
            # Переменные для сглаживания и фильтрации
            smoothed_volume = 0.0
            silence_threshold = 0.001  # Порог тишины
            last_spike_time = 0
            
            while self.running:
                try:
                    # Получаем текущий уровень громкости от VRChat (от 0.0 до 1.0)
                    peak_value = volume_interface.GetPeakValue()
                    
                    # Применяем экспоненциальное сглаживание с настраиваемым коэффициентом
                    if peak_value > silence_threshold:
                        smoothed_volume = self.smoothing_alpha * peak_value + (1 - self.smoothing_alpha) * smoothed_volume
                    else:
                        smoothed_volume *= 0.95  # Медленное затухание
                    
                    current_time = time.time()
                    
                    # Отправляем данные для визуализации
                    self.audio_queue.put(('volume_update', smoothed_volume))
                    
                    # Обнаруживаем резкий скачок громкости (звук клева)
                    if smoothed_volume > self.audio_threshold:
                        # Проверяем cooldown чтобы избежать дублирования
                        if current_time - last_spike_time > self.spike_cooldown:
                            self.audio_queue.put(('sound_detected', smoothed_volume))
                            last_spike_time = current_time
                            logger.info(f"ЗВУК ОБНАРУЖЕН! Громкость: {smoothed_volume:.4f}, порог: {self.audio_threshold:.4f}")
                    
                    time.sleep(0.05)  # Проверяем каждые 50мс
                    
                except Exception as e:
                    if self.running:
                        self.log_message(f"Ошибка чтения аудио: {e}")
                    break
            
            self.log_message("Мониторинг аудио остановлен")
            
        except Exception as e:
            self.log_message(f"Ошибка инициализации аудио: {e}")
            self.log_message("Убедитесь, что VRChat воспроизводит звук")
    
    def wait_for_bite(self):
        """Ожидание клева рыбы"""
        self.log_message("Жду клев рыбы...")
        self.status_var.set("Жду клев рыбы...")
        
        start_time = time.time()
        
        # Очищаем очередь от старых событий
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        
        if self.cooldown_after_cast > 0:
            self.log_message(f"Пауза {self.cooldown_after_cast:.0f} сек после заброса...")
        
        while self.running and not self.paused:
            try:
                elapsed = time.time() - start_time
                
                # Проверяем звуки только после cooldown периода
                if elapsed > self.cooldown_after_cast:
                    # Обрабатываем ВСЕ события в очереди
                    events_to_process = []
                    while True:
                        try:
                            event = self.audio_queue.get_nowait()
                            events_to_process.append(event)
                        except queue.Empty:
                            break
                    
                    # Проверяем, есть ли событие sound_detected
                    for event, volume in events_to_process:
                        if event == 'sound_detected':
                            self.log_message(f"Обнаружен звук клева! Громкость: {volume:.3f}")
                            # Очищаем очередь и возвращаемся
                            while not self.audio_queue.empty():
                                try:
                                    self.audio_queue.get_nowait()
                                except queue.Empty:
                                    break
                            return True
                else:
                    # Во время cooldown очищаем очередь чтобы не накапливались события
                    while not self.audio_queue.empty():
                        try:
                            self.audio_queue.get_nowait()
                        except queue.Empty:
                            break
                    
                    # Обновляем статус с обратным отсчётом
                    remaining = self.cooldown_after_cast - elapsed
                    if remaining > 0:
                        self.status_var.set(f"Пауза после заброса... ({remaining:.1f}с)")
                
                # Таймаут для избежания бесконечного ожидания
                if elapsed > 300:  # 5 минут максимум
                    self.log_message("Таймаут ожидания клева")
                    return False
                
                time.sleep(0.1)
                
            except Exception as e:
                self.log_message(f"Ошибка при ожидании клева: {e}")
                return False
        
        return False
    
    def reel_in_fish(self):
        """Подсечка и вытаскивание рыбы"""
        self.log_message("Начинаю подсечку...")
        self.status_var.set("Подсекаю рыбу...")
        
        # Начинаем удерживать E
        if not self.activate_vrchat_window():
            return False
        
        # Нажимаем и удерживаем E
        win32api.keybd_event(self.VK_E, 0, 0, 0)
        
        start_time = time.time()
        last_sound_time = time.time()  # Время последнего обнаруженного звука
        music_playing = False
        fish_caught = False
        
        self.log_message(f"Слушаю музыку подсечки... (порог: {self.music_threshold:.3f}, доп. время: {self.additional_wait:.1f}с)")
        
        while self.running and not self.paused:
            elapsed = time.time() - start_time
            
            # Проверяем, прошло ли минимальное время
            if elapsed >= self.min_reel_time:
                # Обрабатываем ВСЕ события в очереди
                current_volume = 0.0
                events_to_process = []
                
                while True:
                    try:
                        event = self.audio_queue.get_nowait()
                        events_to_process.append(event)
                    except queue.Empty:
                        break
                
                # Проверяем текущую громкость
                for event, volume in events_to_process:
                    if event == 'volume_update':
                        current_volume = volume
                    elif event == 'sound_detected':
                        # Звук обнаружен - если это громкая музыка, обновляем время
                        if volume > self.music_threshold:
                            last_sound_time = time.time()
                            music_playing = True
                            self.log_message(f"Музыка играет! Громкость: {volume:.3f}")
                
                # Проверяем, играет ли музыка (громкость выше порога музыки)
                if current_volume > self.music_threshold:
                    last_sound_time = time.time()
                    if not music_playing:
                        music_playing = True
                        self.log_message("Музыка началась - продолжаю подсечку")
                
                # Если музыка играла и прошло больше дополнительного времени после её окончания
                time_since_last_sound = time.time() - last_sound_time
                
                if music_playing and time_since_last_sound > self.additional_wait:
                    self.log_message(f"Музыка закончилась {time_since_last_sound:.1f} сек назад - завершаю подсечку")
                    fish_caught = True
                    break
                
                # Обновляем статус
                if music_playing:
                    if time_since_last_sound < self.additional_wait:
                        self.status_var.set(f"Музыка играет... ({time_since_last_sound:.1f}с)")
                    else:
                        self.status_var.set(f"Ожидание завершения... ({time_since_last_sound:.1f}/{self.additional_wait}с)")
            
            # Таймаут для подсечки (максимум 120 секунд на всякий случай)
            if elapsed > 120:
                self.log_message("Таймаут подсечки (120 сек)")
                break
            
            time.sleep(0.1)
        
        # Отпускаем клавишу E
        win32api.keybd_event(self.VK_E, 0, self.KEYEVENTF_KEYUP, 0)
        
        # Очищаем очередь после завершения
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        
        if fish_caught:
            self.log_message(f"Рыба успешно поймана за {elapsed:.1f} секунд")
        else:
            self.log_message("Подсечка завершена без результата")
        
        return fish_caught
    
    def fishing_cycle(self):
        """Основной цикл рыбалки"""
        self.log_message("Запущен цикл рыбалки")
        
        cycle_count = 0
        
        while self.running:
            if self.paused:
                time.sleep(1)
                continue
            
            try:
                cycle_count += 1
                self.log_message(f"=== Цикл рыбалки #{cycle_count} ===")
                
                # 1. Заброс удочки
                if not self.cast_fishing_line():
                    self.log_message("Ошибка заброса, пропускаю цикл")
                    time.sleep(5)
                    continue
                
                # Небольшая пауза после заброса
                time.sleep(1)
                
                # 2. Ожидание клева
                if not self.wait_for_bite():
                    self.log_message("Клев не обнаружен, повторяю заброс")
                    continue
                
                # 3. Подсечка и вытаскивание
                self.reel_in_fish()
                
                # Пауза между циклами
                self.log_message("Пауза перед следующим циклом...")
                time.sleep(3)
                
            except Exception as e:
                self.log_message(f"Ошибка в цикле рыбалки: {e}")
                time.sleep(5)
        
        self.log_message("Цикл рыбалки завершен")
    
    def start_bot(self):
        """Запуск бота"""
        # Обновляем настройки из GUI
        self.cast_duration = self.cast_duration_var.get()
        self.min_reel_time = self.min_reel_time_var.get()
        self.audio_threshold = self.audio_threshold_var.get()
        self.music_threshold = self.music_threshold_var.get()
        self.additional_wait = self.additional_wait_var.get()
        self.cooldown_after_cast = self.cooldown_after_cast_var.get()
        self.spike_cooldown = self.spike_cooldown_var.get()
        self.smoothing_alpha = self.smoothing_alpha_var.get()
        
        # Автоматически сохраняем настройки при запуске
        self.save_settings()
        
        # Проверяем наличие VRChat
        if not self.find_vrchat_window():
            messagebox.showerror("Ошибка", "VRChat не найден! Убедитесь, что игра запущена.")
            return
        
        self.running = True
        self.paused = False
        
        # Запускаем поток мониторинга аудио
        self.audio_thread = threading.Thread(target=self.start_audio_monitoring, daemon=True)
        self.audio_thread.start()
        
        # Запускаем основной поток бота
        self.bot_thread = threading.Thread(target=self.fishing_cycle, daemon=True)
        self.bot_thread.start()
        
        # Запускаем обработку очереди визуализации
        self.process_audio_queue()
        
        # Обновляем интерфейс
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_var.set("Бот запущен")
        
        self.log_message("Бот запущен!")
    
    def process_audio_queue(self):
        """Обработка очереди аудио событий в главном потоке GUI"""
        try:
            # Обрабатываем только события volume_update для визуализации
            # События sound_detected обрабатываются в потоке бота
            processed_count = 0
            max_process = 10  # Ограничим количество за один вызов
            
            while not self.audio_queue.empty() and processed_count < max_process:
                try:
                    event, value = self.audio_queue.get_nowait()
                    
                    if event == 'volume_update':
                        # Обновляем визуализацию
                        self.update_volume_visualization(value)
                        processed_count += 1
                    else:
                        # Возвращаем событие sound_detected обратно в очередь
                        # для обработки в потоке бота
                        self.audio_queue.put((event, value))
                        break
                        
                except queue.Empty:
                    break
                    
        except Exception as e:
            logger.error(f"Ошибка обработки очереди: {e}")
        
        # Продолжаем обработку, если бот работает
        if self.running:
            self.root.after(50, self.process_audio_queue)  # Каждые 50мс
    
    def stop_bot(self):
        """Остановка бота"""
        self.running = False
        self.paused = False
        
        # Ждем завершения потоков
        if self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join(timeout=2)
        
        if self.bot_thread and self.bot_thread.is_alive():
            self.bot_thread.join(timeout=2)
        
        # Обновляем интерфейс
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_var.set("Бот остановлен")
        
        self.log_message("Бот остановлен!")
    
    def run(self):
        """Запуск приложения"""
        self.log_message("VRChat Fishing Bot готов к работе")
        self.log_message("Убедитесь, что VRChat запущен и находится в режиме рыбалки")
        
        # Обработка закрытия окна
        def on_closing():
            if self.running:
                self.stop_bot()
            self.root.destroy()
        
        self.root.protocol("WM_DELETE_WINDOW", on_closing)
        self.root.mainloop()

if __name__ == "__main__":
    try:
        bot = VRChatFishingBot()
        bot.run()
    except KeyboardInterrupt:
        print("Программа прервана пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        input("Нажмите Enter для выхода...")