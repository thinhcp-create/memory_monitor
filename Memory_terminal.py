import sys
import serial
import serial.tools.list_ports
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QTextEdit,
    QMessageBox, QTableWidget, QTableWidgetItem
)
from PyQt5.QtCore import QThread, pyqtSignal
import sys
import serial
import serial.tools.list_ports
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QTextEdit,
    QMessageBox, QTableWidget, QTableWidgetItem
)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
import time

class SerialReader(QThread):
    data_received = pyqtSignal(bytes)
    timeout_signal = pyqtSignal()

    def __init__(self, serial_port, timeout=2.0):
        super().__init__()
        self.serial = serial_port
        self.running = True
        self.timeout = timeout
        self.last_data_time = 0
        # self.retry_count = 0
        self.retry_done = False


    def run(self):
        while self.running:
            if self.serial.in_waiting:
                try:
                    data = self.serial.read(self.serial.in_waiting)
                    print(data)
                    self.data_received.emit(data)
                    self.last_data_time = time.time()
                except:
                    pass
            elif self.last_data_time > 0 and (time.time() - self.last_data_time) > self.timeout:

                if not self.retry_done:
                        # Retry lần 1
                    try:
                        self.serial.write(self.last_command.encode())  # bạn cần lưu lại lệnh cuối cùng đã gửi
                        self.retry_done = True
                        self.last_data_time = time.time()  # reset lại timer
                        print("Thực hiện retry...")
                        print(self.last_command.encode())
                    except:
                        self.timeout_signal.emit()
                        self.last_data_time = 0
                else:
                    self.timeout_signal.emit()
                    self.last_data_time = 0
                    self.retry_done = False

    def stop(self):
        self.running = False
        self.quit()
        self.wait()


class SerialApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flash read monitor")
        self.serial = None
        self.reader_thread = None
        self.buffer = b""
        self.expected_size = 0
        self.start_address = 0
        self.current_address = 0
        self.end_address = 0
        self.chunk_size = 0x10  # Kích thước mỗi lần đọc (16 bytes)
        self.read_timeout = 2000  # Timeout mỗi lần đọc (ms)
        self.read_timer = QTimer()
        self.read_timer.timeout.connect(self.handle_read_timeout)
        self.is_reading = False

        self.init_ui()
        self.refresh_ports()
        self.resize(1100, 600)
        self.showMaximized()

    def init_ui(self):
        layout = QVBoxLayout()

        # Port selection
        port_row = QHBoxLayout()
        self.port_combo = QComboBox()
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["115200", "9600", "57600", "38400"])
        self.connect_btn = QPushButton("Kết nối")
        self.connect_btn.clicked.connect(self.toggle_connection)
        port_row.addWidget(QLabel("Cổng:"))
        port_row.addWidget(self.port_combo)
        port_row.addWidget(QLabel("Baud:"))
        port_row.addWidget(self.baud_combo)
        port_row.addWidget(self.connect_btn)
        layout.addLayout(port_row)

        # Address input
        addr_row = QHBoxLayout()
        self.start_input = QLineEdit()
        self.end_input = QLineEdit()
        self.start_input.setPlaceholderText("Địa chỉ bắt đầu (hex)")
        self.end_input.setPlaceholderText("Địa chỉ kết thúc (hex)")
        self.send_btn = QPushButton("Gửi lệnh đọc")
        self.send_btn.clicked.connect(self.send_read_command)
        addr_row.addWidget(QLabel("Từ:"))
        addr_row.addWidget(self.start_input)
        addr_row.addWidget(QLabel("Đến:"))
        addr_row.addWidget(self.end_input)
        addr_row.addWidget(self.send_btn)
        layout.addLayout(addr_row)
        # Search by address
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Nhập địa chỉ cần tìm (hex)")
        self.search_btn = QPushButton("Tìm")
        self.search_btn.clicked.connect(self.search_address)
        search_row.addWidget(QLabel("Tìm địa chỉ:"))
        search_row.addWidget(self.search_input)
        search_row.addWidget(self.search_btn)
        layout.addLayout(search_row)

        # Table to display data
        self.table = QTableWidget()
        self.table.setColumnCount(17)  # 1 cột địa chỉ + 16 byte
        headers = ["Address"] + [f"+{i:X}" for i in range(16)]
        self.table.setHorizontalHeaderLabels(headers)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        self.setLayout(layout)

    def refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        self.port_mapping = {}
        for p in ports:
            label = f"{p.device} - {p.description}"
            self.port_mapping[label] = p.device
            self.port_combo.addItem(label)

    def toggle_connection(self):
        if self.serial and self.serial.is_open:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self):
        try:
            selected = self.port_combo.currentText()
            port = self.port_mapping.get(selected, selected)
            baud = int(self.baud_combo.currentText())
            self.serial = serial.Serial(port, baud, timeout=1)
            self.reader_thread = SerialReader(self.serial)
            self.reader_thread.data_received.connect(self.handle_data)
            self.reader_thread.start()
            self.connect_btn.setText("Ngắt")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    def disconnect_serial(self):
        if self.reader_thread:
            self.reader_thread.stop()
        if self.serial:
            self.serial.close()
        self.connect_btn.setText("Kết nối")

    def send_read_command(self):
        if not self.serial or not self.serial.is_open:
            QMessageBox.warning(self, "Chưa kết nối", "Bạn chưa kết nối tới cổng COM.")
            return
        
        try:
            self.start_address = int(self.start_input.text(), 16)
            self.end_address = int(self.end_input.text(), 16)
            
            if self.start_address >= self.end_address:
                raise ValueError("Địa chỉ bắt đầu phải nhỏ hơn kết thúc.")
            
            self.current_address = self.start_address
            self.buffer = b""
            self.expected_size = self.end_address - self.start_address
            self.bytes_shown = 0
            self.table.setRowCount(0)
            self.is_reading = True
            
            # Bắt đầu quá trình đọc tuần tự
            self.read_next_chunk()
            
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", str(e))

    def read_next_chunk(self):
        if self.current_address >= self.end_address or not self.is_reading:
            self.is_reading = False
            self.read_timer.stop()
            return
            
        chunk_end = min(self.current_address + self.chunk_size, self.end_address)
        cmd = f"#w01 READ:{self.current_address},{chunk_end}.*"
        self.serial.write(cmd.encode())
        print(f"Gửi lệnh: {cmd.strip()}")
        self.reader_thread.last_command = cmd  # Gán cho thread để dùng khi retry
        # Bắt đầu đếm timeout
        self.read_timer.start(self.read_timeout)

    # def handle_data(self, data):
    #     try:
    #         # Nếu đang trong quá trình đọc tuần tự thì dừng timer timeout
    #         if self.is_reading:
    #             self.read_timer.stop()
                
    #         text = data.decode(errors="ignore")
    #         lines = text.strip().splitlines()
    #         for line in lines:
    #             self.parse_and_fill(line.strip())
                
    #         # Nếu đang trong quá trình đọc tuần tự thì đọc chunk tiếp theo
    #         if self.is_reading:
    #             self.read_next_chunk()
                
    #     except Exception as e:
    #         print(f"Lỗi giải mã dữ liệu: {e}")
    def handle_data(self, data):
        try:
            # Nếu đang trong quá trình đọc tuần tự thì dừng timer timeout
            if self.is_reading:
                self.read_timer.stop()

            # Tạo bộ đệm nếu chưa có
            if not hasattr(self, 'line_buffer'):
                self.line_buffer = b""

            # Gom thêm dữ liệu vào buffer
            self.line_buffer += data

            # Xử lý từng dòng hoàn chỉnh (kết thúc bằng \n hoặc *)
            while b"\n" in self.line_buffer or b"*" in self.line_buffer:
                # Ưu tiên tách theo dấu kết thúc sớm nhất
                newline_pos = self.line_buffer.find(b"\n")
                star_pos = self.line_buffer.find(b".*")
                split_pos = min(pos for pos in [newline_pos, star_pos] if pos != -1)

                line = self.line_buffer[:split_pos]
                self.line_buffer = self.line_buffer[split_pos + 1:]

                text_line = line.decode(errors="ignore").strip()
                if text_line:
                    self.parse_and_fill(text_line)

            # Nếu đang trong quá trình đọc tuần tự thì đọc chunk tiếp theo
            # if self.is_reading:
            #     self.read_next_chunk()

        except Exception as e:
            print(f"Lỗi giải mã dữ liệu: {e}")

    def handle_read_timeout(self):
        if self.is_reading:
            self.is_reading = False
            QMessageBox.warning(self, "Timeout", 
                              f"Không nhận được dữ liệu khi đọc từ địa chỉ {self.current_address:X}")
            self.read_timer.stop()

    def parse_and_fill(self, line):
        if ':' not in line:
            return
            
        try:
            addr_str, hex_data = line.split(":")
            addr = int(addr_str, 16)
            hex_data = hex_data.strip().replace(" ", "")
            bytes_data = bytes.fromhex(hex_data)
            
            # Cập nhật current_address nếu đang trong quá trình đọc tuần tự
            if self.is_reading:
                self.current_address = addr + len(bytes_data)
            
            # Hiển thị dữ liệu
            row_index = self.table.rowCount()
            for i in range(0, len(bytes_data), 16):
                chunk = bytes_data[i:i+16]
                self.table.insertRow(self.table.rowCount())
                self.table.setItem(row_index, 0, QTableWidgetItem(f"{addr + i:08X}"))
                for j, byte in enumerate(chunk):
                    self.table.setItem(row_index, j + 1, QTableWidgetItem(f"{byte:02X}"))
                row_index += 1
            self.table.resizeColumnsToContents()
            time.sleep(0.1)  # Thêm một chút thời gian để UI có thể cập nhật
            self.read_next_chunk()
            
        except Exception as e:
            print(f"Lỗi phân tích dòng: {line} -> {e}")


    def fill_table(self, data):
        base = self.start_address + self.bytes_shown
        remaining = len(data) - self.bytes_shown

        rows_to_add = (remaining + 15) // 16  # làm tròn lên
        for i in range(rows_to_add):
            row_start = self.bytes_shown + i * 16
            row_end = min(row_start + 16, len(data))
            self.table.insertRow(self.table.rowCount())

            # Địa chỉ đúng tại thời điểm này
            row_addr = self.start_address + row_start
            self.table.setItem(self.table.rowCount() - 1, 0, QTableWidgetItem(f"{row_addr:08X}"))

            for col in range(16):
                index = row_start + col
                if index < len(data):
                    val = data[index]
                    self.table.setItem(self.table.rowCount() - 1, col + 1, QTableWidgetItem(f"{val:02X}"))
                else:
                    self.table.setItem(self.table.rowCount() - 1, col + 1, QTableWidgetItem(""))

        self.bytes_shown += rows_to_add * 16
        self.table.resizeColumnsToContents()

    def search_address(self):
        try:
            addr = int(self.search_input.text(), 16)
            offset = addr - self.start_address
            if offset < 0 or offset >= self.table.rowCount() * 16:
                raise ValueError("Địa chỉ ngoài vùng đã hiển thị.")

            row = offset // 16
            col = (offset % 16) + 1  # +1 vì cột 0 là Addr

            self.table.setCurrentCell(row, col)
            self.table.scrollToItem(self.table.item(row, col))
        except Exception as e:
            QMessageBox.warning(self, "Lỗi tìm kiếm", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SerialApp()
    window.show()
    sys.exit(app.exec_())
