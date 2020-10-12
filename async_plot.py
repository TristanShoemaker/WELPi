import time
import libmc
from streamlit_pi import streamPlot, message


def run():
    message("Async plot startup")
    mc = libmc.Client(['localhost'])
    while True:
        stp = streamPlot()
        stp.makeWEL(['-t', '12'])
        plots = stp.plotAssembly()
        mc_result = mc.set('plotKey', plots)
        if not mc_result:
            raise(F"{time.strftime('%Y-%m-%d %H:%M')} : Plot failed to Cache")
        time.sleep(59)


run()
