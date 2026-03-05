from libstp import seq, Mission, wait_for_checkpoint, wait_for_button, loop_forever, slow_servo

from src.steps.drum_lifting_step import drum_lifting_service_up
from src.hardware.defs import Defs
from src.steps.drum_collector import drum_retreat
from src.steps.drum_pusher_servo import open_drum_pusher, close_drum_pusher


class PotatoMission(Mission):
    def sequence(self) -> "Step":
        return seq([

            #drum_lifting_service_up()
            slow_servo(Defs.lift_drums_servo, 30, 5)

        ])


#loop_forever(seq([
 #               open_drum_pusher(),
  #               wait_for_button(),
   #             # wait_for_checkpoint(11),
    ##            close_drum_pusher(),
      #          drum_retreat(),
#
 #           ])),