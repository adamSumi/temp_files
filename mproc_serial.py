import multiprocessing
import serial
import time
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Header, Footer, Input, RichLog, Button, Static
from textual.message import Message
from textual import work

# ==============================================================================
# 1. THE MULTIPROCESSING SERIAL BACKEND
#    (This runs in a completely separate CPU process)
# ==============================================================================

def serial_worker_process(port, baud, write_queue, read_queue, stop_event):
    """
    The independent process that owns the serial port.
    """
    ser = None
    try:
        ser = serial.Serial(port, baud, timeout=0.1)
        # Signal that we are ready
        read_queue.put(b"[SYSTEM] PORT OPENED\r\n")
        
        while not stop_event.is_set():
            # 1. Handle Writing
            if not write_queue.empty():
                try:
                    data = write_queue.get_nowait()
                    ser.write(data)
                except:
                    pass

            # 2. Handle Reading
            if ser.in_waiting > 0:
                try:
                    # Read all available bytes
                    data = ser.read(ser.in_waiting)
                    if data:
                        read_queue.put(data)
                except:
                    pass
            
            # Prevent CPU hogging
            time.sleep(0.01)

    except Exception as e:
        read_queue.put(f"[SYSTEM] ERROR: {e}\r\n".encode())
    finally:
        if ser and ser.is_open:
            ser.close()

# ==============================================================================
# 2. THE TEXTUAL APPLICATION
#    (This runs in the main process/thread)
# ==============================================================================

class SerialRxMessage(Message):
    """Custom Textual Message sent when data arrives from the queue."""
    def __init__(self, data: bytes) -> None:
        self.data = data
        super().__init__()

class ATTerminalApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    RichLog {
        border: solid green;
        height: 1fr;
        background: $surface;
    }
    Input {
        dock: bottom;
        border: solid yellow;
    }
    #status_bar {
        height: 3;
        dock: bottom;
        background: $accent;
        color: auto;
        content-align: center middle;
    }
    """

    def __init__(self, port, baud):
        super().__init__()
        self.port = port
        self.baud = baud
        
        # Setup Multiprocessing Primitives
        self.write_queue = multiprocessing.Queue()
        self.read_queue = multiprocessing.Queue()
        self.stop_event = multiprocessing.Event()
        self.proc = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="log", highlight=True, markup=True)
        yield Input(placeholder="Type AT Command and press Enter...", id="cmd_input")
        yield Footer()

    def on_mount(self) -> None:
        """App has started. Launch the background process and the bridge worker."""
        
        # 1. Start the Serial Process
        self.proc = multiprocessing.Process(
            target=serial_worker_process,
            args=(self.port, self.baud, self.write_queue, self.read_queue, self.stop_event)
        )
        self.proc.start()
        
        # 2. Start the Bridge Worker (Polls the queue)
        self.poll_serial_queue()
        
        self.query_one(RichLog).write(f"[bold green]Connected to {self.port} @ {self.baud}[/]")

    def on_unmount(self) -> None:
        """App is closing. Clean up processes."""
        self.stop_event.set()
        if self.proc:
            self.proc.join(timeout=1)

    # --------------------------------------------------------------------------
    # THE BRIDGE WORKER
    # --------------------------------------------------------------------------
    @work(exclusive=True, thread=True)
    def poll_serial_queue(self):
        """
        Runs in a thread. Watches the multiprocessing queue.
        When data appears, posts a message to the main UI thread.
        """
        while not self.stop_event.is_set():
            try:
                # Blocking get with short timeout to allow checking stop_event
                data = self.read_queue.get(timeout=0.1)
                # Send data to the UI thread via message
                self.post_message(SerialRxMessage(data))
            except multiprocessing.queues.Empty:
                continue
            except Exception as e:
                # Handle unexpected errors
                break

    # --------------------------------------------------------------------------
    # EVENT HANDLERS
    # --------------------------------------------------------------------------
    def on_serial_rx_message(self, message: SerialRxMessage) -> None:
        """Receives data from the bridge worker and updates the UI."""
        log = self.query_one(RichLog)
        
        # Decode bytes to string for display
        try:
            text = message.data.decode('utf-8', errors='replace')
            log.write(text.strip())
        except Exception:
            log.write(str(message.data))

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """User pressed Enter."""
        cmd = event.value
        if cmd:
            # Send to Process
            cmd_bytes = cmd.encode('utf-8') + b'\r\n'
            self.write_queue.put(cmd_bytes)
            
            # Echo to UI
            self.query_one(RichLog).write(f"[bold yellow]>> {cmd}[/]")
            
            # Clear input
            event.input.value = ""

# ==============================================================================
# RUNNER
# ==============================================================================
if __name__ == "__main__":
    # CONFIG
    PORT = "/dev/ttyUSB0" # Change this!
    BAUD = 115200

    app = ATTerminalApp(PORT, BAUD)
    app.run()
