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

#ifndef GRAPHANALYSIS_H
#define GRAPHANALYSIS_H

#include <algorithm>
#include <QMainWindow>
#include <QListWidgetItem>
#include <QProcess>
#include <QScrollBar>
#include <QCollator>
#include "mtracecheck.h"

namespace Ui {
class GraphAnalysis;
}

class GraphAnalysis : public QMainWindow
{
  Q_OBJECT

public:
  explicit GraphAnalysis(QWidget *parent = 0);
  ~GraphAnalysis();
  void addParent(MTraceCheck *parentParam);
  void addDirectory(std::string *jjj);
  void createList();

private slots:
  void on_actionExit_triggered();

  void on_actionOpen_Directory_triggered();

  void on_listWidget_itemDoubleClicked(QListWidgetItem *item);

  void on_listWidget_2_itemDoubleClicked(QListWidgetItem *item);

  void on_pushButton_clicked();

  void on_actionZoom_In_triggered();

  void on_actionZoom_Out_triggered();

  void on_actionGraph_1_triggered();

  void on_actionGraph_2_triggered();

  void on_actionGraph_compared_triggered();

private:
  QString *generatePNG(QListWidgetItem *item);
  void adjustScrollBar(QScrollBar *scrollBar, double factor);
  void scaleImage(double factor);
  MTraceCheck *parent;
  bool graph1Loaded;
  bool graph2Loaded;
  double scaleFactor[3];
  Ui::GraphAnalysis *ui;
};

#endif // GRAPHANALYSIS_H
