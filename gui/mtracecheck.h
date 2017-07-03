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

#ifndef MTRACECHECK_H
#define MTRACECHECK_H

#include <QMainWindow>
#include <QFileDialog>
#include <QPixmap>

namespace Ui {
class MTraceCheck;
}

class MTraceCheck : public QMainWindow
{
  Q_OBJECT

public:
  explicit MTraceCheck(QWidget *parent = 0);
  ~MTraceCheck();
  void closeTestGen();
  void closeSigGen();
  void closeGraphAnalysis();

private slots:
  void on_actionExit_triggered();

  void on_actionOpen_Window_triggered();

  void on_actionOpen_config_file_triggered();

  void on_actionOpen_Window_2_triggered();

  void on_actionOpen_Window_3_triggered();

private:
  Ui::MTraceCheck *ui;
  bool flagTestGen;
  bool flagSigGen;
  bool flagGraphAnalysis;

  // Configuration parameters
};

#endif // MTRACECHECK_H
