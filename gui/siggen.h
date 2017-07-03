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

#ifndef SIGGEN_H
#define SIGGEN_H

#include <QMainWindow>
#include <string>
#include "mtracecheck.h"

namespace Ui {
class SigGen;
}

class SigGen : public QMainWindow
{
  Q_OBJECT

public:
  explicit SigGen(QWidget *parent = 0);
  ~SigGen();
  void addParent(MTraceCheck *parentParam);
  void addDirectory(std::string *jjj);

private slots:
  void on_actionExit_triggered();

private:
  MTraceCheck *parent;
  Ui::SigGen *ui;
};

#endif // SIGGEN_H
