// File:          supervisor.cpp
// Date:
// Description:
// Author:
// Modifications:

#include <webots/Robot.hpp>
#include <webots/Supervisor.hpp>
#include <webots/Emitter.hpp>
#include <cstdio>

using namespace webots;

// helper functions

// this function prints the score of both teams
void setScore(int teamA_score, int teamB_score, Supervisor* supervisor) {
  supervisor->setLabel(0, std::to_string(teamA_score), 0.92, 0.01, 0.1, 
                                                      0x0000ff, 0.0, "Arial");
  supervisor->setLabel(1, std::to_string(teamB_score), 0.05, 0.01, 0.1, 
                                                      0xffff00, 0.0, "Arial");
}
void setTime(std::string time_string, Supervisor* supervisor) {
  supervisor->setLabel(2, time_string, 0.45, 0.01, 0.1, 
                                              0x000000, 0.0, "Arial");
}
void resetBallPosition(Field* ballTranslationField, Field* ballRotationField,
            const double* ballStartPosition, const double* ballStartRotation) {
  ballTranslationField->setSFVec3f(ballStartPosition);
  ballRotationField->setSFRotation(ballStartRotation);
}
void resetRobotPosition(Field* robotTranslationField, 
  Field* robotRotationField, const double* robotStartPosition, 
  const double* robotStartRotation) {
  robotTranslationField->setSFVec3f(robotStartPosition);
  robotRotationField->setSFRotation(robotStartRotation);
}

int main(int argc, char **argv) {
  // create the Supervisor instance.
  Supervisor *supervisor = new Supervisor();
  
  // get game settings from the world info (DEF GAME_SETTINGS).
  // this is the time unit of the simulation
  Node *node = supervisor->getFromDef("GAME_SETTINGS");
  // the definition of time step (ms/step)
  int timeStep = (int)supervisor->getBasicTimeStep();

  // Provide safe defaults in case the GAME_SETTINGS node or its fields
  // are missing or malformed (avoids crashing when the PROTO is not
  // correctly parsed). These match the defaults used previously in
  // the world file.
  int robotsCount = 2;
  double goalXLimit = 0.745;
  int gameTimeMinutes = 10;

  if (node) {
    // Try to read each field; if a field is missing, keep the default.
    Field *f = node->getField("robots");
    if (f)
      robotsCount = f->getSFInt32();

    f = node->getField("goalXLimit");
    if (f)
      goalXLimit = f->getSFFloat();

    f = node->getField("gameTimeMinutes");
    if (f)
      gameTimeMinutes = f->getSFInt32();
  } else {
    fprintf(stderr, "WARNING: GAME_SETTINGS node not found — using defaults\n");
  }
  double gameTimeSeconds = gameTimeMinutes * 60.0;
  // initial fields
  Field *robotTranslationField[robotsCount];
  Field *robotRotationField[robotsCount];
  Field *ballTranslationField;
  Field *ballRotationField;
  // ball spawn position
  node = supervisor->getFromDef("BALL");
  const double* ballStartPosition = 
                                  node->getField("translation")->getSFVec3f();
  const double* ballStartRotation = 
                                  node->getField("rotation")->getSFRotation();
  ballTranslationField = node->getField("translation");
  ballRotationField = node->getField("rotation");
  // initial robot start positions and rotations
  node = supervisor->getFromDef("R0");
  const double* robotAStartPosition = 
                                  node->getField("translation")->getSFVec3f();
  const double* robotAStartRotation =     
                                  node->getField("rotation")->getSFRotation();
  robotTranslationField[0] = node->getField("translation");
  robotRotationField[0] = node->getField("rotation");
  node = supervisor->getFromDef("R1");
  const double* robotBStartPosition = 
                                  node->getField("translation")->getSFVec3f();
  const double* robotBStartRotation =
                                  node->getField("rotation")->getSFRotation();
  robotTranslationField[1] = node->getField("translation");
  robotRotationField[1] = node->getField("rotation");
  // initial runtime robots and ball positions
  const double* robotsPositions[2];
  const double* robotsRotations[2];
  const double* ballPosition;
  robotsPositions[0] = robotAStartPosition;
  robotsPositions[1] = robotBStartPosition;
  robotsRotations[0] = robotAStartRotation;
  robotsRotations[1] = robotBStartRotation;
  ballPosition = ballStartPosition;
  // initial score
  int score[2] = {0, 0};
  // inital emitter
  Emitter *emitter = supervisor->getEmitter("emitter");
  // inital data packet
  double packet[robotsCount * 3 + 2];
  // inital time_string
  char timeString[64];
  // inital ball reset timer
  double ballResetTimer = 0.0;
  // inital set score
  setScore(score[0], score[1], supervisor);
  // inital timers
  double gameTimer = gameTimeSeconds;
  // double ballResetTimer = 0.0;

  while (supervisor->step(timeStep) != -1) {
    ballPosition = ballTranslationField->getSFVec3f();
    for (int i = 0; i < robotsCount; i++) {
      robotsPositions[i] = robotTranslationField[i]->getSFVec3f();
      packet[3 * i] = robotsPositions[i][0];     // robot i: X
      packet[3 * i + 1] = robotsPositions[i][1];  // robot i: Y
      robotsRotations[i] = robotRotationField[i]->getSFRotation();
      if (robotsRotations[i][2] > 0)               // robot i: rotation Rz axis
        packet[3 * i + 2] = robotsRotations[i][3];  // robot i: alpha
      else                                         // Rz axis was inverted
        packet[3 * i + 2] = -robotsRotations[i][3];
    }
    packet[3 * robotsCount] = ballPosition[0];      // ball X
    packet[3 * robotsCount + 1] = ballPosition[1];  // ball Y
    // send data packet to robots
    emitter->send(packet, sizeof(packet));

    // subtract time step to the timer
    gameTimer -= (double)timeStep / 1000.0;
    if (gameTimer < 0.0) {
      // time is up, end the game
      gameTimer = gameTimeSeconds;  // restart
      score[0] = 0;
      score[1] = 0;
      setScore(score[0], score[1], supervisor);
      // reset robots and ball positions
      resetRobotPosition(robotTranslationField[0], robotRotationField[0],
                          robotAStartPosition, robotAStartRotation);
      resetRobotPosition(robotTranslationField[1], robotRotationField[1],
                          robotBStartPosition, robotBStartRotation);
      resetBallPosition(ballTranslationField, ballRotationField,
                          ballStartPosition, ballStartRotation);
    }
    sprintf(timeString, "%02d:%02d", 
            (int)(gameTimer / 60), (int)((int)gameTimer % 60));
    setTime(timeString, supervisor);

    if (ballPosition[0] < -goalXLimit) {
      // goal for team B
      score[1] += 1;
      setScore(score[0], score[1], supervisor);
      // reset ball positions
      resetBallPosition(ballTranslationField, ballRotationField,
                          ballStartPosition, ballStartRotation);
    } else if (ballPosition[0] > goalXLimit) {
      // goal for team A
      score[0] += 1;
      setScore(score[0], score[1], supervisor);
      // reset ball positions
      resetBallPosition(ballTranslationField, ballRotationField,
                          ballStartPosition, ballStartRotation);
    }

  };

  // Enter here exit cleanup code.
  delete supervisor;

  return 0;
}
