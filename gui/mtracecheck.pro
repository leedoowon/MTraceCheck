#-------------------------------------------------
#
# Project created by QtCreator 2016-11-24T16:11:00
#
#-------------------------------------------------

QT       += core gui

greaterThan(QT_MAJOR_VERSION, 4): QT += widgets

TARGET = mtracecheck
TEMPLATE = app


SOURCES += main.cpp\
        mtracecheck.cpp \
    siggen.cpp \
    graphanalysis.cpp \
    testgen.cpp

HEADERS  += mtracecheck.h \
    siggen.h \
    graphanalysis.h \
    testgen.h

FORMS    += mtracecheck.ui \
    siggen.ui \
    graphanalysis.ui \
    testgen.ui
