from win32 import win32gui

def list_open_windows():
    """
    Returns a list of all open window names/titles in Windows 10.
    Only includes visible windows with a title.
    
    Returns:
        list: A list of window titles as strings
    """
    def enum_windows_callback(hwnd, window_list):
        if win32gui.IsWindowVisible(hwnd):
            window_title = win32gui.GetWindowText(hwnd)
            if window_title:
                window_list.append(window_title)
        return True
    
    windows = []
    win32gui.EnumWindows(enum_windows_callback, windows)
    return windows

def print_open_windows():
    """
    Prints all open window names to console
    """
    windows = list_open_windows()
    print("Open Windows:")
    for i, window in enumerate(windows, 1):
        print(f"{i}. {window}")

if __name__ == "__main__":
    # Example usage when script is run directly
    print_open_windows()
