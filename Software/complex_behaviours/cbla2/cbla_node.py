__author__ = 'Matthew'

from time import clock

from abstract_node.node import *
from interactive_system import Messenger

import cbla_engine


class CBLA_Node(Node):

    def __init__(self, messenger: Messenger, teensy_name: str, data_collector: cbla_engine.DataCollector,
                 node_name='cbla_node'):


        if not isinstance(teensy_name, str):
            raise TypeError('teensy_name must be a string!')

        self.teensy_name = teensy_name

        # reference to the data collector
        self.data_collector = data_collector

        super(CBLA_Node, self).__init__(messenger, node_name='%s.%s' % (teensy_name, node_name))

        self.state_save_period = 200  # seconds

        self.cbla_robot = None
        self.cbla_learner = None

    def instantiate(self, learner_config=None):

        if self.cbla_robot is None:
            raise AttributeError("CBLA_Robot must be implemented in the child class")

        # create learner
        M0 = self.cbla_robot.compute_initial_motor()
        S0 = self.cbla_robot.read()

        # load previous learner expert
        try:
            past_state = self.data_collector.data_file['state'][self.node_name]
        except KeyError:
            past_state = None

        if not isinstance(learner_config, dict):
            learner_config = dict()
        self.cbla_learner = cbla_engine.Learner(S0, M0, past_state=past_state, idle_mode_enable=True,
                                                **learner_config)

        # load previous learner steps
        config = dict()
        try:
            config['update_count_start'] = past_state['learner_step']
        except KeyError:
            pass

        # create CBLA engine
        self.cbla_engine = cbla_engine.CBLA_Engine(self.cbla_robot, self.cbla_learner, **config)

        # internal output variables
        self.out_var['S'] = self.cbla_robot.S0
        self.out_var['M'] = self.cbla_robot.M0

        # output variables
        self.out_var['loop_time'] = Var(0)
        self.out_var['idle_mode'] = Var(False)
        self.out_var['node_step'] = Var(0)
        self.out_var['best_val'] = Var(0)

        self.cbla_states = dict()

    def run(self):

        # add information about the robot's label to data_collector
        label_info = dict()
        if 'in_vars_name' in self.cbla_robot.config:
            label_info['input_label_name'] = self.cbla_robot.config['in_vars_name']
        if 'out_vars_name' in self.cbla_robot.config:
            label_info['output_label_name'] = self.cbla_robot.config['out_vars_name']

        if label_info:
            self.data_collector.update_state(node_name=self.node_name, states_update=label_info)

        last_save_states_time = clock()
        while self.alive:
            # adjust the robot's wait time between act() and read()
            self.cbla_robot.curr_wait_time = max(self.cbla_robot.config['wait_time'],
                                                 self.messenger.estimated_msg_period * 6)

            # update CBLA Engine
            data_packet = self.cbla_engine.update()

            # save the data
            self.data_collector.append_data_packet(self.node_name, data_packet)

            self.out_var['loop_time'].val = data_packet['loop_period']
            self.out_var['idle_mode'].val = data_packet['in_idle_mode']
            self.out_var['node_step'].val = data_packet['step']
            self.out_var['best_val'].val = data_packet['best_action_value']

            # cbla_engine.CBLA_Engine.print_data_packet(data_packet, header=self.node_name)

            # save state periodically
            curr_time = clock()
            if curr_time - last_save_states_time > self.state_save_period:
                self.save_states()
                last_save_states_time = curr_time

        self.save_states()

    def save_states(self):

        with self.cbla_engine.learner_lock:
            # save state when terminated
            self.cbla_states['learner_expert'] = self.cbla_engine.learner.expert
            self.cbla_states['learner_step'] = self.cbla_engine.update_count

        self.data_collector.update_state(self.node_name, self.cbla_states)


class CBLA_Tentacle(CBLA_Node):

    def __init__(self, messenger: Messenger, teensy_name: str, data_collector: cbla_engine.DataCollector,
                 ir_0: Var=Var(0), ir_1: Var=Var(0), acc: Var=Var(0),
                 left_ir: Var=Var(0), right_ir: Var=Var(0), shared_ir_0: Var=Var(0),
                 frond: Var=Var(0), reflex_0: Var=Var(0), reflex_1: Var=Var(0), node_name='cbla_tentacle'):


        super(CBLA_Tentacle, self).__init__(messenger=messenger, teensy_name=teensy_name,
                                            data_collector=data_collector, node_name=node_name)

        # defining the input variables
        self.in_var['ir_0'] = ir_0
        self.in_var['ir_1'] = ir_1
        self.in_var['acc_x'] = acc.val[0]
        self.in_var['acc_y'] = acc.val[1]
        self.in_var['acc_z'] = acc.val[2]
        self.in_var['left_ir'] = left_ir
        self.in_var['right_ir'] = right_ir
        self.in_var['shared_ir_0'] = shared_ir_0

        # defining the output variables
        self.out_var['tentacle_out'] = frond
        self.out_var['reflex_out_0'] = reflex_0
        self.out_var['reflex_out_1'] = reflex_1

        # defining the input variables
        in_vars = [self.in_var['acc_x'], self.in_var['acc_y'], self.in_var['acc_z'], self.in_var['shared_ir_0']]
        in_vars_range = [(-512, 512), (-512, 512), (-512, 512), (0, 4095)]
        in_vars_name = ['Accelerometer (x-axis)', 'Accelerometer (y-axis)', 'Accelerometer (z-axis)', 'Shared IR Sensor']

        # defining the output variables
        out_vars = [self.out_var['tentacle_out']]
        out_vars_name = ['motion type']

        # learner configuration
        learner_config = dict()
        learner_config['split_thres'] = 30
        learner_config['split_thres_growth_rate'] = 1.2
        learner_config['split_lock_count_thres'] = 5
        learner_config['mean_err_thres'] = 0.015
        learner_config['reward_smoothing'] = 1
        learner_config['kga_delta'] = 2
        learner_config['kga_tau'] = 4

        # create robot
        self.cbla_robot = cbla_engine.Robot_Frond(in_vars, out_vars, in_vars_range=in_vars_range,
                                                  in_vars_name=in_vars_name, out_vars_name=out_vars_name)

        # instantiate
        self.instantiate(learner_config=learner_config)


class CBLA_Protocell(CBLA_Node):

    def __init__(self, messenger: Messenger, teensy_name: str, data_collector: cbla_engine.DataCollector,
                 als: Var=Var(0), shared_ir_0: Var=Var(0),
                 led: Var=Var(0), node_name='cbla_protocell'):

        super(CBLA_Protocell, self).__init__(messenger=messenger, teensy_name=teensy_name,
                                             data_collector=data_collector, node_name=node_name)

        # defining the input variables
        self.in_var['als'] = als
        self.in_var['shared_ir_0'] = shared_ir_0

        # defining the output variables
        self.out_var['protocell_out'] = led

        # in_vars = [self.in_var['als']]  # one-LED-one-ALS version
        in_vars = [self.in_var['als'], self.in_var['shared_ir_0']]

        in_vars_range = [(0, 4096), (0, 4096)]
        in_vars_name = ['ambient light sensor', 'Shared IR Sensor']

        out_vars = [self.out_var['protocell_out']]
        out_vars_name = ['LED brightness']

        # learner configuration
        learner_config = dict()
        learner_config['split_thres'] = 600
        learner_config['split_thres_growth_rate'] = 1.5
        learner_config['split_lock_count_thres'] = 250
        learner_config['mean_err_thres'] = 0.015
        learner_config['reward_smoothing'] = 1
        learner_config['kga_delta'] = 10
        learner_config['kga_tau'] = 25

        # create robot
        self.cbla_robot = cbla_engine.Robot_Protocell(in_vars, out_vars, in_vars_range=in_vars_range,
                                                      in_vars_name=in_vars_name, out_vars_name=out_vars_name)

        self.instantiate(learner_config=learner_config)