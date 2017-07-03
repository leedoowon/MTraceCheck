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

#include <QDebug>
#include "testgen.h"
#include "ui_testgen.h"

TestGen::TestGen(QWidget *parent) :
  QMainWindow(parent),
  ui(new Ui::TestGen)
{
  ui->setupUi(this);
  this->setCentralWidget(ui->horizontalWidget);
  this->numNonTextBrowserWidgets = -1;
}

TestGen::~TestGen()
{
  delete ui;
}

void TestGen::addParent(MTraceCheck *parentParam)
{
  this->parent = parentParam;
}

void TestGen::on_actionExit_triggered()
{
  /* Terminate Signature Generation window */
  this->parent->closeTestGen();
  this->close();
}

void TestGen::runPythonScript(QProcess &process, QStringList &arguments)
{
  bool ret_start, ret_finish;
  QString cmd = "C:/Python27/python";  // FIXME
  QString arg;
  foreach(arg, arguments)
    ui->textBrowserOutput->append(arg);
  process.start(cmd, arguments);
  ret_start = process.waitForStarted();
  qWarning("Return code start %d\n", ret_start);
  ret_finish = process.waitForFinished();
  qWarning("Return code finish %d\n", ret_finish);
}

void TestGen::on_pushButton_clicked()
{
  /* Generate test */
  // 1. Check line edit components
  int paramThread = ui->lineEdit_thread->text().toInt();
  int paramOp = ui->lineEdit_op->text().toInt();
  int paramLoc = ui->lineEdit_loc->text().toInt();
  int paramExec = ui->lineEdit_exec->text().toInt();
  int paramRand = ui->lineEdit_rand->text().toInt();

  // 2. Command line options for gen_mtrand.py
  QString workDir = "D:/Programming/demo_mtracecheck/exp/161129_demo_graph";  // FIXME
  QDir logDir(workDir + "/log");
  QDir asmDir(workDir + "/asm");
  QStringList args_gen, args_dot, args_prof, args_code;

  args_gen << "D:/Programming/demo_mtracecheck/src/gen_mtrand.py";  // FIXME
  args_gen << "--gen-program" << "--prog-file=prog.txt" << "--wo-file=wo.txt" << "--no-dump-files";
  args_gen << ("--threads=" + QString::number(paramThread));
  args_gen << ("--insts=" + QString::number(paramOp));
  args_gen << ("--locs=" + QString::number(paramLoc));
  args_gen << ("--execs=0");
  args_gen << ("--rand-seed=" + QString::number(paramRand));
  if (ui->comboBox->currentText() == "x86") {
    args_gen << "--consistency-model=tso";
  } else if (ui->comboBox->currentText() == "ARM") {
    args_gen << "--consistency-model=wo";
  } else {
    qFatal("Error: ISA not recognized\n");
  }
  args_dot << "D:/Programming/demo_mtracecheck/src/create_dot_graph.py";  // FIXME
  args_dot << "--out-dir=log" << "--program-file=prog.txt" << "--wo-file=wo.txt" << "hist.txt";

  args_prof << "D:/Programming/demo_mtracecheck/src/value_profiler.py";  // FIXME
  args_prof << "--output=test.txt" << "--no-profile" << "prog.txt";

  args_code << "D:/Programming/demo_mtracecheck/src/codegen.py";  // FIXME
  if (ui->comboBox->currentText() == "x86") {
    args_code << "--arch=x86" << "--reg-width=64";
  } else if (ui->comboBox->currentText() == "ARM") {
    args_code << "--arch=arm" << "--reg-width=32";
  } else {
    qFatal("Error: ISA not recognized\n");
  }
  args_code << "--dir=asm" << "--prefix=test_t" << "--suffix=.S" << "--cpp-file=test_manager.cpp";
  args_code << ("--mem-locs=" + QString::number(paramLoc));
  args_code << ("--execs=" + QString::number(paramExec));
  args_code << "--data-addr=0x100000" << "--data-file=data.bin" << "--bss-addr=0x1000000" << "--bss-size-per-thread=0x1000000" << "--bss-file=bss.bin";
  args_code << "--profile-file=profile.txt" << "--no-print" << "--platform=baremetal" << "--stride-type=2" << "test.txt";
  //qDebug() << cmd_python;
  //qDebug() << args_gen;

  // 3. Clean directories
  if (logDir.exists())
    logDir.removeRecursively();
  if (asmDir.exists())
    asmDir.removeRecursively();
  if (this->numNonTextBrowserWidgets == -1)
    this->numNonTextBrowserWidgets = ui->verticalLayout->count();
  for (int i = ui->verticalLayout->count() - 1; i >= this->numNonTextBrowserWidgets; i--) {
    ui->verticalLayout->removeItem(ui->verticalLayout->takeAt(i));
  }

  QProcess process;
  process.setWorkingDirectory(workDir);

  // 4. Execute python scripts
  this->runPythonScript(process, args_gen);
  this->runPythonScript(process, args_dot);
  this->runPythonScript(process, args_prof);
  this->runPythonScript(process, args_code);

  // 5. Create panels to show generated code
  for (int t = 0; t < paramThread; t++) {
    QTextBrowser *newTextBrowser = new QTextBrowser();
    ui->verticalLayout->addWidget(newTextBrowser);
    QString asmFileName = workDir + "/asm/test_t" + QString::number(t) + ".S";
    qWarning("Read asm file %s\n", asmFileName.toLatin1().constData());
    QFile asmFilePtr(asmFileName);
    if (!asmFilePtr.exists()) {
      qWarning("file does not exist %s\n", asmFileName.toLatin1().constData());
      continue;
    }
    if (!asmFilePtr.open(QIODevice::ReadOnly)) {
      qWarning("file open error %s\n", asmFileName.toLatin1().constData());
      continue;
    }
    QTextStream textStream(&asmFilePtr);
    QString textContent;
    textContent = textStream.readAll();
    newTextBrowser->setText(textContent);
    newTextBrowser->setFont(QFontDatabase::systemFont(QFontDatabase::FixedFont));
  }
}

void TestGen::on_pushButton_2_clicked()
{
  // Simulate test
  // NOTE: This function generates the test as well as

  // 1. Check line edit components
  int paramThread = ui->lineEdit_thread->text().toInt();
  int paramOp = ui->lineEdit_op->text().toInt();
  int paramLoc = ui->lineEdit_loc->text().toInt();
  int paramExec = ui->lineEdit_exec->text().toInt();
  int paramRand = ui->lineEdit_rand->text().toInt();

  // 2. Command line options for gen_mtrand.py
  QString workDir = "D:/Programming/demo_mtracecheck/exp/161129_demo_graph";  // FIXME
  QDir logDir(workDir + "/log");
  QDir asmDir(workDir + "/asm");
  QStringList args_gen, args_dot, args_prof, args_code;

  args_gen << "D:/Programming/demo_mtracecheck/src/gen_mtrand.py";  // FIXME
  args_gen << "--gen-program" << "--prog-file=prog.txt" << "--wo-file=wo.txt" << "--no-dump-files";
  args_gen << ("--threads=" + QString::number(paramThread));
  args_gen << ("--insts=" + QString::number(paramOp));
  args_gen << ("--locs=" + QString::number(paramLoc));
  args_gen << ("--execs=" + QString::number(paramExec));
  args_gen << ("--rand-seed=" + QString::number(paramRand));
  if (ui->comboBox->currentText() == "x86") {
    args_gen << "--consistency-model=tso";
  } else if (ui->comboBox->currentText() == "ARM") {
    args_gen << "--consistency-model=wo";
  } else {
    qFatal("Error: ISA not recognized\n");
  }
  args_dot << "D:/Programming/demo_mtracecheck/src/create_dot_graph.py";  // FIXME
  args_dot << "--out-dir=log" << "--program-file=prog.txt" << "--wo-file=wo.txt" << "hist.txt";

  args_prof << "D:/Programming/demo_mtracecheck/src/value_profiler.py";  // FIXME
  args_prof << "--output=test.txt" << "--no-profile" << "prog.txt";

  args_code << "D:/Programming/demo_mtracecheck/src/codegen.py";  // FIXME
  if (ui->comboBox->currentText() == "x86") {
    args_code << "--arch=x86" << "--reg-width=64";
  } else if (ui->comboBox->currentText() == "ARM") {
    args_code << "--arch=arm" << "--reg-width=32";
  } else {
    qFatal("Error: ISA not recognized\n");
  }
  args_code << "--dir=asm" << "--prefix=test_t" << "--suffix=.S" << "--cpp-file=test_manager.cpp";
  args_code << ("--mem-locs=" + QString::number(paramLoc));
  args_code << ("--execs=" + QString::number(paramExec));
  args_code << "--data-addr=0x100000" << "--data-file=data.bin" << "--bss-addr=0x1000000" << "--bss-size-per-thread=0x1000000" << "--bss-file=bss.bin";
  args_code << "--profile-file=profile.txt" << "--no-print" << "--platform=baremetal" << "--stride-type=2" << "test.txt";
  //qDebug() << cmd_python;
  //qDebug() << args_gen;

  // 3. Clean directories
  if (logDir.exists())
    logDir.removeRecursively();
  if (asmDir.exists())
    asmDir.removeRecursively();
  if (this->numNonTextBrowserWidgets == -1)
    this->numNonTextBrowserWidgets = ui->verticalLayout->count();
  for (int i = ui->verticalLayout->count() - 1; i >= this->numNonTextBrowserWidgets; i--) {
    ui->verticalLayout->removeItem(ui->verticalLayout->takeAt(i));
  }

  QProcess process;
  process.setWorkingDirectory(workDir);

  // 4. Execute python scripts
  this->runPythonScript(process, args_gen);
  this->runPythonScript(process, args_dot);
  this->runPythonScript(process, args_prof);
  this->runPythonScript(process, args_code);

  // 5. Create panels to show generated code
  for (int t = 0; t < paramThread; t++) {
    QTextBrowser *newTextBrowser = new QTextBrowser();
    ui->verticalLayout->addWidget(newTextBrowser);
    QString asmFileName = workDir + "/asm/test_t" + QString::number(t) + ".S";
    qWarning("Read asm file %s\n", asmFileName.toLatin1().constData());
    QFile asmFilePtr(asmFileName);
    if (!asmFilePtr.exists()) {
      qWarning("file does not exist %s\n", asmFileName.toLatin1().constData());
      continue;
    }
    if (!asmFilePtr.open(QIODevice::ReadOnly)) {
      qWarning("file open error %s\n", asmFileName.toLatin1().constData());
      continue;
    }
    QTextStream textStream(&asmFilePtr);
    QString textContent;
    textContent = textStream.readAll();
    newTextBrowser->setText(textContent);
    newTextBrowser->setFont(QFontDatabase::systemFont(QFontDatabase::FixedFont));
  }
}

void TestGen::on_pushButton_3_clicked()
{
  // Compile for ARM

  // 1. Check line edit components
  int paramThread = ui->lineEdit_thread->text().toInt();
  int paramOp = ui->lineEdit_op->text().toInt();
  int paramLoc = ui->lineEdit_loc->text().toInt();
  int paramExec = ui->lineEdit_exec->text().toInt();
  int paramRand = ui->lineEdit_rand->text().toInt();

  // 2. Command line options for gen_mtrand.py
  QString workDir = "D:/Programming/demo_mtracecheck/exp/161129_demo_graph";  // FIXME
  QDir logDir(workDir + "/log");
  QDir asmDir(workDir + "/asm");
  QStringList args_gen, args_prof_no_profile, args_prof_profile, args_code;

  args_gen << "D:/Programming/demo_mtracecheck/src/gen_mtrand.py";  // FIXME
  args_gen << "--gen-program" << "--prog-file=prog.txt" << "--wo-file=wo.txt" << "--no-dump-files";
  args_gen << ("--threads=" + QString::number(paramThread));
  args_gen << ("--insts=" + QString::number(paramOp));
  args_gen << ("--locs=" + QString::number(paramLoc));
  args_gen << ("--execs=0");
  args_gen << ("--rand-seed=" + QString::number(paramRand));
  args_gen << "--consistency-model=wo";
  if (ui->comboBox->currentText() != "ARM") {
    qWarning("Warning: ISA must be set to ARM... Overriding your choice %s\n", ui->comboBox->currentText().toLatin1().constData());
  }
  args_prof_profile << "D:/Programming/demo_mtracecheck/src/value_profiler.py";  // FIXME
  args_prof_profile << "--output=test.txt" << "prog.txt";
  args_prof_no_profile << "D:/Programming/demo_mtracecheck/src/value_profiler.py";  // FIXME
  args_prof_no_profile << "--output=test.txt" << "--no-profile" << "prog.txt";

  args_code << "D:/Programming/demo_mtracecheck/src/codegen.py";  // FIXME
  args_code << "--arch=arm" << "--reg-width=32";
  if (ui->comboBox->currentText() != "ARM") {
    qWarning("Warning: ISA must be set to ARM... Overriding your choice %s\n", ui->comboBox->currentText().toLatin1().constData());
  }
  args_code << "--dir=asm" << "--prefix=test_t" << "--suffix=.S" << "--cpp-file=test_manager.cpp";
  args_code << ("--mem-locs=" + QString::number(paramLoc));
  args_code << ("--execs=" + QString::number(paramExec));
  args_code << "--data-addr=0x50000000" << "--data-file=data.bin" << "--bss-addr=0x60000000" << "--bss-size-per-thread=0x1000000" << "--bss-file=bss.bin";
  args_code << "--profile-file=profile.txt" << "--no-print" << "--platform=baremetal" << "--stride-type=2" << "test.txt";
  //qDebug() << cmd_python;
  //qDebug() << args_gen;

  // 3. Clean directories
  if (logDir.exists())
    logDir.removeRecursively();
  if (asmDir.exists())
    asmDir.removeRecursively();
  if (this->numNonTextBrowserWidgets == -1)
    this->numNonTextBrowserWidgets = ui->verticalLayout->count();
  for (int i = ui->verticalLayout->count() - 1; i >= this->numNonTextBrowserWidgets; i--) {
    ui->verticalLayout->removeItem(ui->verticalLayout->takeAt(i));
  }

  QProcess process;
  process.setWorkingDirectory(workDir);

  // 4. Execute python scripts (before displaying)
  this->runPythonScript(process, args_gen);
  this->runPythonScript(process, args_prof_no_profile);
  this->runPythonScript(process, args_code);

  // 5. Create panels to show generated code
  for (int t = 0; t < paramThread; t++) {
    QTextBrowser *newTextBrowser = new QTextBrowser();
    ui->verticalLayout->addWidget(newTextBrowser);
    QString asmFileName = workDir + "/asm/test_t" + QString::number(t) + ".S";
    qWarning("Read asm file %s\n", asmFileName.toLatin1().constData());
    QFile asmFilePtr(asmFileName);
    if (!asmFilePtr.exists()) {
      qWarning("file does not exist %s\n", asmFileName.toLatin1().constData());
      continue;
    }
    if (!asmFilePtr.open(QIODevice::ReadOnly)) {
      qWarning("file open error %s\n", asmFileName.toLatin1().constData());
      continue;
    }
    QTextStream textStream(&asmFilePtr);
    QString textContent;
    textContent = textStream.readAll();
    newTextBrowser->setText(textContent);
    newTextBrowser->setFont(QFontDatabase::systemFont(QFontDatabase::FixedFont));
  }

  // 6. Execute python scripts (after displaying)
  this->runPythonScript(process, args_prof_profile);
  this->runPythonScript(process, args_code);
}

void TestGen::on_pushButton_4_clicked()
{
  /*  python dump_to_sig.py capture.log a
   *  python signature_decoder.py --profile-file=../exp/160812_codegen_x86/profile.txt --output=hist_decoded.txt ../exp/160812_codegen_x86/signature1.txt
   *  python create_dot_graph.py -v --out-dir=log --gen-tsort --program-file=../exp/160812_codegen_x86/prog.txt --wo-file=../exp/160812_codegen_x86/wo.txt --ignore-reg hist_decoded.txt
  */
  QString workDir = "D:/Programming/demo_mtracecheck/exp/161129_demo_graph";  // FIXME
  QDir logDir(workDir + "/log");
  //QDir asmDir(workDir + "/asm");
  QStringList args_dump, args_decode, args_dot;

  args_dump << "D:/Programming/demo_mtracecheck/src/dump_to_sig.py";  // FIXME
  args_dump << "capture.log" << "signature.txt";

  args_decode << "D:/Programming/demo_mtracecheck/src/signature_decoder.py";  // FIXME
  args_decode << "--profile-file=profile.txt" << "--output=hist_decoded.txt" << "signature.txt";

  args_dot << "D:/Programming/demo_mtracecheck/src/create_dot_graph.py";  // FIXME
  args_dot << "--out-dir=log" << "--program-file=prog.txt" << "--wo-file=wo.txt" << "--ignore-reg" << "hist_decoded.txt";

  if (logDir.exists()) {
    foreach(QString dirFile, logDir.entryList())
      logDir.remove(dirFile);
  }

  QProcess process;
  process.setWorkingDirectory(workDir);

  // Execute python scripts
  this->runPythonScript(process, args_dump);
  this->runPythonScript(process, args_decode);
  this->runPythonScript(process, args_dot);
}
