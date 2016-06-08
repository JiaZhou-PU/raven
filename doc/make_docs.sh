#!/bin/bash

SCRIPT_NAME=`readlink $0`
if test -x "$SCRIPT_NAME";
then
    SCRIPT_DIRNAME=`dirname $SCRIPT_NAME`
else
    SCRIPT_DIRNAME=`dirname $0`
fi
SCRIPT_DIR=`(cd $SCRIPT_DIRNAME; pwd)`
cd $SCRIPT_DIR

VERB=0
for i in "$@"
do
  if [[ $i == "--verbose" ]]
  then
    VERB=1
    echo Entering verbose mode...
  fi
done

rm -Rvf pdfs

for DIR in  user_manual user_guide qa_docs tests; do
    cd $DIR
    echo Building in $DIR...
    if [[ 1 -eq $VERB ]]
    then
      make; MADE=$?
    else
      make > /dev/null; MADE=$?
    fi
    if [[ 0 -eq $MADE ]]; then
        echo ...Successfully made docs in $DIR
    else
        echo ...Failed to make docs in $DIR
        exit -1
    fi
    cd $SCRIPT_DIR
done

mkdir pdfs
for DOC in user_guide/raven_user_guide.pdf qa_docs/raven_sdd.pdf qa_docs/test_plan.pdf qa_docs/requirements.pdf  user_manual/raven_user_manual.pdf tests/analytic_tests.pdf; do
    cp $DOC pdfs/
done

