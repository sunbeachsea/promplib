#!/usr/bin/env python
# -*- coding: utf-8 -*-

from promp.interactive import InteractiveProMP
from baxter_commander import ArmCommander
from kinect2.client import Kinect2Client
import rospy

rospy.init_node('vocal_interactive_promps')

class VocalInteractiveProMPs(object):
    def __init__(self, arm='left'):
        # MOTION
        self.promp = InteractiveProMP(arm)
        self.arm = ArmCommander(arm, ik='robot')
        self.init = self.arm.get_current_state()

        # INTERACTION (TTS + Speech recognition -- Kinect)
        rospy.loginfo("setting up the kinect...")
        self.kinect = Kinect2Client('BAXTERFLOWERS.local')
        self.kinect.tts.params.queue_on()
        self.kinect.tts.params.set_language('english')
        self.kinect.tts.start()
        self.kinect.speech.params.set_confidence(0.5)
        self.kinect.speech.params.set_vocabulary({'Record a motion': 'record',
                                                  'Set a goal': 'goal',
                                                  'ready': 'ready',
                                                  'stop': 'stop'}, language="en-US")
        self.kinect.display_speech()
        success = self.kinect.speech.start()  # start with no callback to use the get() method
        assert success == '', success
        rospy.loginfo("Kinect started!")

    def read_user_input(self, all_semantics):
        speech = self.kinect.speech.get()
        if all_semantics is not None and speech is not None:
            if 'semantics' in speech:
                word = speech['semantics'][0]  # TODO we might have received several words?
                if word in all_semantics:
                    return word
        return ""

    def record_motion(self):
        for countdown in ['ready?', 3, 2, 1, "go"]:
            self.say('{}'.format(countdown), blocking=False)
            rospy.sleep(1)
        self.arm.recorder.start(10)
        rospy.loginfo("Recording...")

        choice = ""
        while choice != 'stop' and not rospy.is_shutdown():
            choice = self.read_user_input(['stop'])

        joints, eef = self.arm.recorder.stop()
        self.say('Motion recorded, please wait...', blocking=False)
        if len(joints.joint_trajectory.points) == 0:
            self.say('This demo is empty, please retry')
        else:
            try:
                self.promp.add_demonstration(joints, eef)
            except ValueError:
                self.say("Sorry I failed to record this demonstration")

    def set_goal(self):
        if self.promp.num_primitives > 0:
            self.say('Move the robot and say ready to set the goal')

            choice = ""
            while choice != 'ready' and not rospy.is_shutdown():
                choice = self.read_user_input(['ready'])

            goal_set = self.promp.set_goal(self.arm.endpoint_pose())
            if goal_set:
                self.say('I can reach this object, let me demonstrate', blocking=False)
                self.arm.move_to_controlled(self.init)
                self.arm.open()
                trajectory = self.promp.generate_trajectory()
                self.arm.execute(trajectory)
                self.arm.close()
                self.arm.translate_to_cartesian([0, 0, 0.2], 'base', 2)
                if self.arm.gripping():
                    self.say('Take it!')
                    self.arm.wait_for_human_grasp(ignore_gripping=False)
                    self.arm.open()
            else:
                self.say("I don't know how to reach this object. {}".format(self.promp.status_writing))
        else:
            self.say('There is no demonstration yet, please record at least one demo')

    def say(self, what, blocking=True):
        rospy.loginfo(what)
        self.kinect.tts.say(what, blocking)

    def run(self):
        while not rospy.is_shutdown():
            self.arm.move_to_controlled(self.init)
            if self.promp.num_demos > 3:
                self.say('Do you want to record a motion or set a new goal?')
                choice = self.read_user_input(['record', 'goal'])
                if choice == 'record':
                    self.record_motion()
                elif choice == 'goal':
                    self.set_goal()
            else:
                self.say("Let's record a {} demo, say stop to finish".format(['first', 'second', 'third', ''][self.promp.num_demos%4]))
                self.record_motion()
            self.say('There are {} primitive{} and {} demonstration{}'.format(self.promp.num_primitives,
                                                                                         's' if self.promp.num_primitives > 1 else '', self.promp.num_demos,
                                                                                         's' if self.promp.num_demos > 1 else ''))

VocalInteractiveProMPs().run()