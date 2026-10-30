"""Low-battery alert policy, independent from the Windows notification API."""


class LowBatteryAlert:
    def __init__(self, threshold=10):
        self.threshold = threshold
        self._alerted_device = None

    def should_notify(self, state):
        if not state.connected or state.percent is None:
            return False
        key = (state.vid, state.pid, state.model_code)
        if state.charging or state.percent > self.threshold:
            if self._alerted_device == key:
                self._alerted_device = None
            return False
        if self._alerted_device == key:
            return False
        self._alerted_device = key
        return True
