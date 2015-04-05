__author__ = 'Matthew'

from time import clock
from abstract_node.node import *
from interactive_system import Messenger
import cbla_engine

class CBLA_Tentacle(Node):

    def __init__(self, messenger: Messenger, teensy_name: str,
                 ir_0: Var=Var(0), ir_1: Var=Var(0), acc: Var=Var(0), cluster_activity: Var=Var(0),
                 left_ir: Var=Var(0), right_ir: Var=Var(0),
                 frond: Var=Var(0), reflex_0: Var=Var(0), reflex_1: Var=Var(0), node_name='cbla_tentacle'):

        if not isinstance(teensy_name, str):
            raise TypeError('teensy_name must be a string!')

        self.teensy_name = teensy_name

        super(CBLA_Tentacle, self).__init__(messenger, node_name='%s.%s' % (teensy_name, node_name))

        # defining the input variables
        self.in_var['ir_0'] = ir_0
        self.in_var['ir_1'] = ir_1
        self.in_var['acc_x'] = acc.val[0]
        self.in_var['acc_y'] = acc.val[1]
        self.in_var['acc_z'] = acc.val[2]
        self.in_var['left_ir'] = left_ir
        self.in_var['right_ir'] = right_ir
        self.in_var['cluster_activity'] = cluster_activity

        # defining the output variables
        self.out_var['tentacle_out'] = frond
        self.out_var['reflex_out_0'] = reflex_0
        self.out_var['reflex_out_1'] = reflex_1
        self.out_var['cluster_activity'] = cluster_activity

        in_vars = [self.in_var['acc_x'], self.in_var['acc_y'], self.in_var['acc_z'], self.in_var['ir_0']]
        out_vars = [self.out_var['tentacle_out']]

        # create robot
        self.cbla_robot = cbla_engine.Robot(in_vars, out_vars)

        # create learner
        M0 = self.cbla_robot.compute_initial_motor()
        S0 = self.cbla_robot.read()
        self.cbla_learner = cbla_engine.Learner(S0, M0)

        # create CBLA engine
        self.cbla_engine = cbla_engine.CBLA_Engine(self.cbla_robot, self.cbla_learner)


    def run(self):

        while True:
            self.cbla_engine.update(robot_wait=self.messenger.estimated_msg_period*2)




