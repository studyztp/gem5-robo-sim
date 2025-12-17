// File:          players.cpp
// Date:
// Description:
// Author:
// Modifications:

#include <webots/Robot.hpp>
#include <webots/Motor.hpp>
#include <webots/TouchSensor.hpp>
#include <webots/Device.hpp>
#include <cstdio>
#include <algorithm>
#include "bridge.hpp"

#include <webots/PositionSensor.hpp>
using namespace webots;

#define MAX_SPEED 100

int main(int argc, char **argv) {
  // create the Robot instance.
  Robot *robot = new Robot();

  // get basic information
  int timeStep = (int)robot->getBasicTimeStep();
  std::string name = robot->getName();

  // get and initialize devices
  TouchSensor *bumper = robot->getTouchSensor("bumper");
  if (bumper)
    bumper->enable(timeStep);
  Motor *leftMotor = robot->getMotor("left wheel motor");
  PositionSensor *leftEnc = robot->getPositionSensor("left wheel sensor");
  PositionSensor *rightEnc = robot->getPositionSensor("right wheel sensor");
  if (leftEnc) leftEnc->enable(timeStep);
  if (rightEnc) rightEnc->enable(timeStep);
  Motor *rightMotor = robot->getMotor("right wheel motor");
  if (!leftMotor || !rightMotor) {
    fprintf(stderr, "error: motors not found\n");
    delete robot;
    return 1;
  }
  const double maxMotorVelocity = leftMotor->getMaxVelocity();
  leftMotor->setPosition(INFINITY);
  rightMotor->setPosition(INFINITY);
  leftMotor->setVelocity(0.0);
  rightMotor->setVelocity(0.0);
  
  double leftSpeed = 1;
  double rightSpeed = 1;
  bool bumped = false;
  int bumpCount = 0;

  // initialize message to compute
  pid_t server_pid = -1;
  int fid = -1;
  if (bridge_setup_client(name, server_pid, fid) != 0) {
    fprintf(stderr, "bridge_setup_client failed for %s\n", name.c_str());
    delete robot;
    return 1;
  }
  // after setup the connection, send the timestep information to the server
  Message msg;
  Message response_msg;
  std::vector<int> message_use_vec;
  msg.command = SETUP_TIMESTEP;
  msg.data.resize(sizeof(int));
  std::memcpy(msg.data.data(), &timeStep, sizeof(int));
  bridge_send_message(fid, msg);
  int data;
  size_t nints;

  while (robot->step(timeStep) != -1) {
    if (bumper->getValue() > 0.0) {
        bumped = true;
        bumpCount++;
    } else {
        bumped = false;
    }

    data = bumped ? 1 : 0;

    msg.command = COMPUTE_REQUEST;
    msg.data.resize(sizeof(int));
    std::memcpy(msg.data.data(), &data, sizeof(int));
    bridge_send_and_wait_for_response(fid, msg, response_msg, -1);
    if (response_msg.command != COMPUTE_RESPONSE) {
      fprintf(stderr, "unexpected response command %d\n", response_msg.command);
      continue;
    }
    size_t bytes = response_msg.data.size();
    if (bytes < 2 * sizeof(int)) {
      fprintf(stderr, "response too small: %zu bytes\n", bytes);
      continue;
    }
    int leftInt = 0, rightInt = 0;
    std::memcpy(&leftInt, response_msg.data.data(), sizeof(int));
    std::memcpy(&rightInt, response_msg.data.data() + sizeof(int), sizeof(int));
    fprintf(stderr, "velocities received: left=%d right=%d\n", leftInt, rightInt);
    leftSpeed = static_cast<double>(leftInt);
    rightSpeed = static_cast<double>(rightInt);
    leftMotor->setVelocity(leftSpeed);
    rightMotor->setVelocity(rightSpeed);
  }
  delete robot;
  return 0;
}
