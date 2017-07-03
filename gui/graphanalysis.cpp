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

#include "graphanalysis.h"
#include "ui_graphanalysis.h"

GraphAnalysis::GraphAnalysis(QWidget *parent) :
  QMainWindow(parent),
  ui(new Ui::GraphAnalysis)
{
  ui->setupUi(this);
  ui->labelGraph->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Ignored);
  ui->labelGraph1->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Ignored);
  ui->labelGraph2->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Ignored);
  ui->labelGraph->setScaledContents(true);
  ui->labelGraph1->setScaledContents(true);
  ui->labelGraph2->setScaledContents(true);
  ui->scrollArea->setWidget(ui->scrollAreaWidgetContents);
  ui->scrollArea_2->setWidget(ui->scrollAreaWidgetContents_2);
  ui->scrollArea_3->setWidget(ui->scrollAreaWidgetContents_3);
  this->setCentralWidget(ui->formWidget);
  this->graph1Loaded = false;
  this->graph2Loaded = false;
  for (int i = 0; i < 3; i++) {
    scaleFactor[i] = 1.0;
  }
}

GraphAnalysis::~GraphAnalysis()
{
  delete ui;
}

void GraphAnalysis::addParent(MTraceCheck *parentParam)
{
  this->parent = parentParam;
}

void GraphAnalysis::createList()
{
  //ui->listWidget->addItem("a123");
  //ui->listWidget->addItem("b456");
  //ui->listWidget_2->addItem("c789");
  //ui->listWidget_2->addItem("d012");
}

void GraphAnalysis::on_actionExit_triggered()
{
  /* Terminate Signature Generation window */
  this->parent->closeGraphAnalysis();
  this->close();
}

bool compareStringNatural(const QFileInfo &info1, const QFileInfo &info2)
{
  QCollator collator;
  collator.setNumericMode(true);
  return collator.compare(info1.baseName(), info2.baseName()) < 0;
}

void GraphAnalysis::on_actionOpen_Directory_triggered()
{
  /* Select directory whose files will be loaded */
  QString dirName = QFileDialog::getExistingDirectory(this, tr("Choose a directory"), "../exp/161129_demo_graph", QFileDialog::ReadOnly);  // FIXME
  if (dirName == NULL)
    return;
  QDir graphDir(dirName);
  QStringList nameFilter;
  nameFilter << "*.dot";
  QFileInfoList graphFiles = graphDir.entryInfoList(nameFilter, QDir::Files, QDir::NoSort);

  std::sort(
        graphFiles.begin(),
        graphFiles.end(),
        compareStringNatural);

  ui->listWidget->clear();
  ui->listWidget_2->clear();
  ui->label->setText(dirName);
  for (QFileInfoList::iterator it = graphFiles.begin(); it != graphFiles.end(); it++) {
    ui->listWidget->addItem(it->baseName());
    ui->listWidget_2->addItem(it->baseName());
  }
}

QString* GraphAnalysis::generatePNG(QListWidgetItem *item)
{
  QString workPath(ui->label->text() + "/");
  QString dotName(workPath + item->text() + ".dot");
  QString *pngName = new QString(workPath + item->text() + ".png");
  QFileInfo fileInfo(*pngName);
  if (!fileInfo.exists() || !fileInfo.isFile()) {
    QString cmd = "C:/Program Files (x86)/Graphviz2.38/bin/neato.exe";  // FIXME
    QStringList arguments;
    arguments << "-n" << "-Tpng" << dotName << ("-o" + *pngName);
    qWarning("Executing %s to generate %s\n", cmd.toLatin1().constData(), pngName->toLatin1().constData());
    int ret = QProcess::execute(cmd, arguments);
    qWarning("Return code %d\n", ret);
  }
  return pngName;
}

void GraphAnalysis::on_listWidget_itemDoubleClicked(QListWidgetItem *item)
{
  /* Item selected */
  //ui->labelSelected1->setText("Rendering...");
  QString *pngName = generatePNG(item);
  QPixmap qp(*pngName);
  ui->labelSelected1->setText(item->text());
  this->scaleFactor[1] = 1.0;
  ui->labelGraph1->setPixmap(qp);
  ui->scrollAreaWidgetContents_2->resize(ui->labelGraph1->pixmap()->size());
  this->graph1Loaded = true;
}

void GraphAnalysis::on_listWidget_2_itemDoubleClicked(QListWidgetItem *item)
{
  /* Item selected */
  //ui->labelSelected2->setText("Rendering...");
  QString *pngName = generatePNG(item);
  QPixmap qp(*pngName);
  ui->labelSelected2->setText(item->text());
  this->scaleFactor[2] = 1.0;
  ui->labelGraph2->setPixmap(qp);
  ui->scrollAreaWidgetContents_3->resize(ui->labelGraph2->pixmap()->size());
  this->graph2Loaded = true;
}

void GraphAnalysis::on_pushButton_clicked()
{
  if (!this->graph1Loaded || !this->graph2Loaded) {
    qWarning("Warning: Either or both of the graphs is not selected\n");
    return;
  }
  QString workPath(ui->label->text() + "/");
  QString pngName1(workPath + ui->labelSelected1->text() + ".png");
  QString pngName2(workPath + ui->labelSelected2->text() + ".png");
  QString diffName(workPath + ui->labelSelected1->text() + "-" + ui->labelSelected2->text() + ".png");
  QFileInfo fileInfo(diffName);
  if (!fileInfo.exists() || !fileInfo.isFile()) {
    QString cmd = "C:/Program Files/ImageMagick-7.0.3-Q16/compare.exe";  // FIXME
    QStringList arguments;
    arguments << pngName1 << pngName2 << diffName;
    qWarning("Executing %s to generate %s\n", cmd.toLatin1().constData(), diffName.toLatin1().constData());
    int ret = QProcess::execute(cmd, arguments);
    qWarning("Return code %d\n", ret);
  }
  QPixmap qp(diffName);
  //ui->labelGraph->setPixmap(qp.scaled(ui->labelGraph->width(), ui->labelGraph->height(), Qt::KeepAspectRatio));
  scaleFactor[0] = 1.0;
  ui->labelGraph->setPixmap(qp);
  ui->scrollAreaWidgetContents->resize(ui->labelGraph->pixmap()->size());
}

void GraphAnalysis::adjustScrollBar(QScrollBar *scrollBar, double factor)
{
  /* This scroll-bar routine is borrowed from imageviewer example in Qt */
  scrollBar->setValue(int(factor * scrollBar->value() + ((factor - 1) * scrollBar->pageStep()/2)));
}

void GraphAnalysis::scaleImage(double factor)
{
  /* This image-scaling routine is borrowed from imageviewer example in Qt */
  int index;
  QScrollArea *scrollAreaPtr;
  QWidget *scrollAreaWidgetContentsPtr;
  QLabel *labelPtr;

  if (ui->actionGraph_compared->isChecked()) {
    index = 0;
    scrollAreaPtr = ui->scrollArea;
    scrollAreaWidgetContentsPtr = ui->scrollAreaWidgetContents;
    labelPtr = ui->labelGraph;
  } else if (ui->actionGraph_1->isChecked()) {
    index = 1;
    scrollAreaPtr = ui->scrollArea_2;
    scrollAreaWidgetContentsPtr = ui->scrollAreaWidgetContents_2;
    labelPtr = ui->labelGraph1;
  } else if (ui->actionGraph_2->isChecked()) {
    index = 2;
    scrollAreaPtr = ui->scrollArea_3;
    scrollAreaWidgetContentsPtr = ui->scrollAreaWidgetContents_3;
    labelPtr = ui->labelGraph2;
  } else {
    qFatal("Error: No graph selected\n");
  }

  Q_ASSERT(labalPtr->pixmap());
  this->scaleFactor[index] *= factor;
  scrollAreaWidgetContentsPtr->resize(this->scaleFactor[index] * labelPtr->pixmap()->size());
  adjustScrollBar(scrollAreaPtr->horizontalScrollBar(), factor);
  adjustScrollBar(scrollAreaPtr->verticalScrollBar(), factor);
}

void GraphAnalysis::on_actionZoom_In_triggered()
{
  this->scaleImage(1.25);
}

void GraphAnalysis::on_actionZoom_Out_triggered()
{
  this->scaleImage(0.8);
}

void GraphAnalysis::on_actionGraph_1_triggered()
{
  ui->actionGraph_compared->setChecked(false);
  ui->actionGraph_1->setChecked(true);
  ui->actionGraph_2->setChecked(false);
}

void GraphAnalysis::on_actionGraph_2_triggered()
{
  ui->actionGraph_compared->setChecked(false);
  ui->actionGraph_1->setChecked(false);
  ui->actionGraph_2->setChecked(true);
}

void GraphAnalysis::on_actionGraph_compared_triggered()
{
  ui->actionGraph_compared->setChecked(true);
  ui->actionGraph_1->setChecked(false);
  ui->actionGraph_2->setChecked(false);
}
