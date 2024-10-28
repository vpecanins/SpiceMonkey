import wx
from Engine import Engine

EVT_RESULT_ID = wx.NewIdRef(count=1)

# Define notification event for communication between threads
class ResultEvent(wx.PyEvent):
    def __init__(self, event_type: str, engine: Engine = None):
        """Init Optimization Result Event."""
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_RESULT_ID)

        # This indicates the type of event
        self.event_type = event_type

        # These are used for optim_step messages
        if engine:
            self.n = engine.n
            self.b_optimized = engine.b_optimized
            self.iteration = engine.iteration
            self.resnorm = engine.resnorm
            self.optimized_vals = engine.optimized_vals
            self.makeup_gain = engine.makeup_gain

            # These are used for parser, solver & optimizer error and info messages
            self.status_msg = engine.status_msg
