/**************************************************************************
 *
 * MTraceCheck
 * Copyright 2017 The Regents of the University of Michigan
 * Doowon Lee and Valeria Bertacco
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 *************************************************************************/

#include "siggen.h"
#include "ui_siggen.h"

SigGen::SigGen(QWidget *parent) :
  QMainWindow(parent),
  ui(new Ui::SigGen)
{
  ui->setupUi(this);
}

SigGen::~SigGen()
{
  delete ui;
}

void SigGen::addParent(MTraceCheck *parentParam)
{
  this->parent = parentParam;
}

void SigGen::on_actionExit_triggered()
{
  /* Terminate Signature Generation window */
  this->parent->closeSigGen();
  this->close();
}
