from libstp import *

from src.hardware.defs import Defs
from src.steps.follow_line_single2_step import follow_line_single2
from src.steps.drum_collector import drum_retreat


class M1000TestMission(Mission):
   def sequence(self) -> Sequential:
       return seq([
           follow_line_single2(
               Defs.front_left_ir_sensor,
               delta_s_cm=3.0,
               beta_deg=15.0,
           ),
           wait_for_button(),
           follow_line_single2(
               Defs.front_left_ir_sensor,
               delta_s_cm=3.0,
               beta_deg=15.0,
           ),
           wait_for_button(),
           follow_line_single2(
               Defs.front_left_ir_sensor,
               delta_s_cm=3.0,
               beta_deg=15.0,
           ),
           wait_for_button(),
           follow_line_single2(
               Defs.front_left_ir_sensor,
               delta_s_cm=3.0,
               beta_deg=15.0,
           ),
           wait_for_button(),
           follow_line_single2(
               Defs.front_left_ir_sensor,
               delta_s_cm=3.0,
               beta_deg=15.0,
           ),
           wait_for_button(),
           follow_line_single2(
               Defs.front_left_ir_sensor,
               delta_s_cm=3.0,
               beta_deg=15.0,
           ),
           wait_for_button(),
           follow_line_single2(
               Defs.front_left_ir_sensor,
               delta_s_cm=3.0,
               beta_deg=15.0,
           ),
           wait_for_button(),
           follow_line_single2(
               Defs.front_left_ir_sensor,
               delta_s_cm=3.0,
               beta_deg=15.0,
           ),
           wait_for_button(),
           follow_line_single2(
               Defs.front_left_ir_sensor,
               delta_s_cm=3.0,
               beta_deg=15.0,
           ),wait_for_button(),
           follow_line_single2(
               Defs.front_left_ir_sensor,
               delta_s_cm=3.0,
               beta_deg=15.0,
           ),




       ])
