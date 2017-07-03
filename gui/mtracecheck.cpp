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

#include <assert.h>
#include "mtracecheck.h"
#include "ui_mtracecheck.h"
#include "testgen.h"
#include "siggen.h"
#include "graphanalysis.h"

MTraceCheck::MTraceCheck(QWidget *parent) :
  QMainWindow(parent),
  ui(new Ui::MTraceCheck)
{
  ui->setupUi(this);
  this->flagTestGen = false;
  this->flagSigGen = false;
  this->flagGraphAnalysis = false;
  ui->label->setScaledContents(true);
  ui->label_2->setScaledContents(true);
  ui->label->setPixmap(QPixmap("D:/Programming/demo_mtracecheck/mtracecheck/logo_umich.png"));
  ui->label_2->setPixmap(QPixmap("D:/Programming/demo_mtracecheck/mtracecheck/logo_cfar.png"));
  this->setCentralWidget(ui->gridWidget);
}

MTraceCheck::~MTraceCheck()
{
  delete ui;
}

void MTraceCheck::closeTestGen()
{
  this->flagTestGen = false;
}

void MTraceCheck::closeSigGen()
{
  this->flagSigGen = false;
}

void MTraceCheck::closeGraphAnalysis()
{
  this->flagGraphAnalysis = false;
}

void MTraceCheck::on_actionExit_triggered()
{
  /* Terminate MTraceCheck GUI */
  this->close();
}

void MTraceCheck::on_actionOpen_Window_triggered()
{
  if (this->flagSigGen) {
    qWarning("Window is open");
    return;
  }
  else {
    this->flagSigGen = true;
  }
  SigGen *sigGenWindow = new SigGen(this);
  sigGenWindow->addParent(this);
  sigGenWindow->show();
}

bool matchString(const char *str1, int idx_begin, int idx_end, const char *str2)
{
  // Check length
  int len_str2 = 0;
  while (str2[len_str2] != 0)
    len_str2++;
  if (len_str2 != (idx_end - idx_begin + 1))
    return false;
  // Check content
  for (int idx = idx_begin, i = 0; idx <= idx_end; idx++, i++) {
    if (str1[idx_begin] != str2[i]) {
      return false;
    }
  }
  return true;
}

void MTraceCheck::on_actionOpen_config_file_triggered()
{
  /* Open a file dialog */
  /* 1. Select a configuration file to be loaded */
  QString fileName = QFileDialog::getOpenFileName(this, tr("Open File"), "", tr("Files(*.*)"));
  if (fileName == NULL)
    return;

  /* 2. Parse contents of file to extract parameters */
  FILE *fpCfg = fopen(fileName.toLatin1().data(), "r");
  if (fpCfg == NULL) {
    qFatal("check configuration file %s\n", fileName.toLatin1().data());
    exit(1);
  }
#define LINE_BUF_SIZE 256
  char line[LINE_BUF_SIZE];
  while (!feof(fpCfg)) {
    // 1. Split line into two tokens, name and value
    const char spliter = ':';
    bool token_found = false;
    int name_idx_begin = 0;
    int name_idx_end = -1;
    int value_idx_begin = -1;
    int value_idx_end = -1;
    fgets(line, LINE_BUF_SIZE, fpCfg);
    for (int i = 0; i < LINE_BUF_SIZE; i++) {
      if (line[i] == 0 || line[i] == '\r' || line[i] == '\n') {
        if (token_found) {
          value_idx_end = i - 1;
        }
        break;
      }
      if (line[i] == spliter) {
        token_found = true;
        name_idx_end = i - 1;
        value_idx_begin = i + 1;
      }
    }
    // 2. Adjust indices to get tight bounds
    if (token_found) {
      assert ((name_idx_begin <= name_idx_end) && (value_idx_begin <= value_idx_end));
      while (line[name_idx_begin] == ' ')
        name_idx_begin++;
      while (line[name_idx_end] == ' ')
        name_idx_end--;
      while (line[value_idx_begin] == ' ')
        value_idx_begin++;
      while (line[value_idx_end] == ' ')
        value_idx_end--;
      assert ((name_idx_begin <= name_idx_end) && (value_idx_begin <= value_idx_end));
    }
    // 3. Select field based on name
    if (token_found) {
      if (matchString(line, name_idx_begin, name_idx_end, "sig_dir")) {
      } else if (matchString(line, name_idx_begin, name_idx_end, "a")) {
      } else if (matchString(line, name_idx_begin, name_idx_end, "b")) {
      } else if (matchString(line, name_idx_begin, name_idx_end, "c")) {
      } else if (matchString(line, name_idx_begin, name_idx_end, "d")) {
      } else {
        // TODO: Warning dialog
      }
    }
  }
  fclose(fpCfg);
}

void MTraceCheck::on_actionOpen_Window_2_triggered()
{
  if (this->flagGraphAnalysis) {
    qWarning("Window is open");
    return;
  }
  else {
    this->flagGraphAnalysis = true;
  }
  GraphAnalysis *graphAnalysisWindow = new GraphAnalysis(this);
  graphAnalysisWindow->addParent(this);
  graphAnalysisWindow->createList();
  graphAnalysisWindow->show();
}

void MTraceCheck::on_actionOpen_Window_3_triggered()
{
  if (this->flagTestGen) {
    qWarning("Window is open");
    return;
  }
  else {
    this->flagTestGen = true;
  }
  TestGen *testGenWindow = new TestGen(this);
  testGenWindow->addParent(this);
  testGenWindow->show();
}
