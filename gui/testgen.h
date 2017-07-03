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

#ifndef TESTGEN_H
#define TESTGEN_H

#include <QMainWindow>
#include <QProcess>
#include <QStringList>
#include <QTextBrowser>
#include <QFontDatabase>
#include "mtracecheck.h"

namespace Ui {
class TestGen;
}

class TestGen : public QMainWindow
{
  Q_OBJECT

public:
  explicit TestGen(QWidget *parent = 0);
  ~TestGen();
  void addParent(MTraceCheck *parentParam);

private slots:
  void on_actionExit_triggered();

  void on_pushButton_clicked();

  void on_pushButton_2_clicked();

  void on_pushButton_3_clicked();

  void on_pushButton_4_clicked();

private:
  void runPythonScript(QProcess &process, QStringList &arguments);
  MTraceCheck *parent;
  int numNonTextBrowserWidgets;
  Ui::TestGen *ui;
};

#endif // TESTGEN_H
