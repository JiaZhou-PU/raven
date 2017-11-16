# Copyright 2017 Battelle Energy Alliance, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Created on Nov 1, 2017

@author: dan maljovec, mandd

"""

from __future__ import division, print_function , unicode_literals, absolute_import
import warnings
warnings.simplefilter('default', DeprecationWarning)

#External Modules---------------------------------------------------------------
import numpy as np
import xml.etree.ElementTree as ET
#External Modules End-----------------------------------------------------------

#Internal Modules---------------------------------------------------------------
from .PostProcessor import PostProcessor
from utils import InputData
from utils import xmlUtils as xmlU
import Files
import Runners
#Internal Modules End-----------------------------------------------------------


class ETimporter(PostProcessor):
  """
    This is the base class for postprocessors
  """
  def __init__(self, messageHandler):
    """
      Constructor
      @ In, messageHandler, MessageHandler, message handler object
      @ Out, None
    """
    PostProcessor.__init__(self, messageHandler)
    self.printTag = 'POSTPROCESSOR ET IMPORTER'
    self.ETformat = None
    self.allowedFormats = ['OpenPSA']


  @classmethod
  def getInputSpecification(cls):
    """
      Method to get a reference to a class that specifies the input data for
      class cls.
      @ In, cls, the class for which we are retrieving the specification
      @ Out, inputSpecification, InputData.ParameterInput, class to use for
        specifying input of cls.
    """
    inputSpecification = super(ETimporter, cls).getInputSpecification()

    return inputSpecification


  def initialize(self, runInfo, inputs, initDict) :
    """
      Method to initialize the pp.
      @ In, runInfo, dict, dictionary of run info (e.g. working dir, etc)
      @ In, inputs, list, list of inputs
      @ In, initDict, dict, dictionary with initialization options
      @ Out, None
    """
    PostProcessor.initialize(self, runInfo, inputs, initDict)
    self.inputs = inputs
    self._workingDir = runInfo['WorkingDir']

  def _localReadMoreXML(self, xmlNode):
    """
      Function to read the portion of the xml input that belongs to this specialized class
      and initialize some stuff based on the inputs got
      @ In, xmlNode, xml.etree.Element, Xml element node
      @ Out, None
    """
    for child in xmlNode:
      if child.tag == 'fileFormat':
        if child.text not in self.allowedFormats:
          self.raiseAnError(IOError, 'ETimporterPostProcessor Post-Processor ' + self.name + ', format ' + child.text + ' : is not supported')
        else:
          self.ETformat = child.text
      else:
        self.raiseAnError(IOError, 'ETimporterPostProcessor Post-Processor ' + self.name + ', node ' + child.tag + ' : is not recognized')

  def run(self, input):
    """
      This method executes the postprocessor action.
      @ In,  input, object, object containing the data to process. (inputToInternal output)
      @ Out, None
    """
    if self.ETformat == 'OpenPSA':
      self.outputDict = self.runOpenPSA(input)

  def runOpenPSA(self, input):
    """
      This method executes the postprocessor action.
      @ In,  input, object, object containing the data to process. (inputToInternal output)
      @ Out, None
    """

    ### Check for link to other ET
    standAloneET   = []
    dependendentET = []

    '''
    for ET in input:
        for node in root.findall('define-sequence'):
            if node.find('event-tree') is not None:
                dependendentET.append(ET)
            else:
                standAloneET.append(ET)

    while len(standAloneET)!= len(input):
        for ET in standAloneET:
   '''
    linkedTree = False
    for files in input:
        outcome = self.checkLinkedTree(input[0].getPath() + input[0].getFilename())
        linkedTree = linkedTree or outcome

    if linkedTree==True and len(input)>1:
        #link trees
        pass

    if linkedTree==False and len(input)>1:
        self.raiseAnError(IOError, 'Multiple ET files have provided but they are not linked')

    if linkedTree==True and len(input)==1:
        self.raiseAnError(IOError, 'A single ET files has provided but it contains a link to an additional ET')

    if linkedTree == False and len(input)==1:
        return self.analyzeSingleET(input[0])


  def analyzeSingleET(self,file):
      eventTree, root = self.checkSubBranches(file.getPath() + file.getFilename())

      ## These outcomes will be encoded as integers starting at 0
      outcomes = []

      ## These self.variables will be mapped into an array where there index
      self.variables = []
      values = {}

      for node in root.findall('define-functional-event'):
          event = node.get('name')

          ## First, map the variable to an index by placing it in a list
          self.variables.append(event)

          ## Also, initialize the dictionary of values for this variable so we can
          ## encode them as integers as well
          values[event] = []

          ## Iterate through the forks that use this event and gather all of the
          ## possible states
          for fork in self.findAllRecursive(eventTree, 'fork'):
              if fork.get('functional-event') == event:
                  for path in fork.findall('path'):
                      state = path.get('state')
                      if state not in values[event]:
                          values[event].append(state)

      ## Iterate through the sequences and gather all of the possible outcomes
      ## so we can numerically encode them latter
      for node in root.findall('define-sequence'):
          outcome = node.get('name')
          if outcome not in outcomes:
              outcomes.append(outcome)
      map = self.returnMap(outcomes, file.name)

      self.raiseADebug("ETimporter variables identified: " + str(format(self.variables)))

      d = len(self.variables)
      n = len(self.findAllRecursive(eventTree, 'sequence'))

      self.pointSet = -1 * np.ones((n, d + 1))
      rowCounter = 0
      for node in eventTree:
          newRows = self.constructPointDFS(node, self.variables, values, map, self.pointSet, rowCounter)
          rowCounter += newRows

      outputDict = {}
      outputDict['inputs'] = {}
      outputDict['outputs'] = {}

      for index, var in enumerate(self.variables):
          outputDict['inputs'][var] = self.pointSet[:, index]

      outputDict['outputs']['sequence'] = self.pointSet[:, -1]

      return outputDict


  def checkLinkedTree(self,file):
      root = ET.parse(file)
      outcome = False
      for node in root.findall('define-sequence'):
          childs = [elem.tag for elem in node.iter() if elem is not node]
          if 'event-tree' in childs:
              outcome = outcome or True
      return outcome

  def checkSubBranches(self,file):
      root = ET.parse(file)

      eventTree = root.findall('initial-state')

      if len(eventTree) > 1:
          self.raiseAnError(IOError, 'ETimporter: more than one initial-state identified')

      eventTree = eventTree[0]

      ### Check for sub-branches
      subBranches = {}
      for node in root.findall('define-branch'):
          subBranches[node.get('name')] = node.find('fork')
          self.raiseADebug("ETimporter branch identified: " + str(node.get('name')))
      if len(subBranches) > 0:
          for node in root.findall('.//'):
              if node.tag == 'path':
                  for subNode in node.findall('branch'):
                      linkName = subNode.get('name')
                      if linkName in subBranches.keys():
                          node.append(subBranches[linkName])
                      else:
                          self.raiseAnError(RuntimeError, ' ETimporter: branch ' + str(
                              linkName) + ' linked in the ET is not defined; available branches are: ' + str(
                              subBranches.keys()))

      Root = root.getroot()
      for child in Root:
          if child.tag == 'branch':
              root.remove(child)

      return eventTree,root

  def returnMap(self,outcomes,name):
      # check if outputMap contains string ID for  at least one sequence
      # if outputMap contains all numbers then keep the number ID
      allFloat = True
      for seq in outcomes:
          try:
              float(seq)
          except ValueError:
              allFloat = False
              break
      map = {}
      if allFloat == False:
          # create an integer map, and
          # create an integer map file
          root = ET.Element('map')
          root.set('Tree', name)
          for seq in outcomes:
              map[seq] = outcomes.index(seq)
              # map.append(outcomes.index(seq))
              ET.SubElement(root, "sequence", ID=str(outcomes.index(seq))).text = str(seq)
          fileID = name + '_mapping.xml'
          updatedTreeMap = ET.ElementTree(root)
          xmlU.prettify(updatedTreeMap)
          updatedTreeMap.write(fileID)
      else:
          for seq in outcomes:
              map[seq] = float(seq)
              #map.append(float(seq))
      return map

  def collectOutput(self,finishedJob, output):
    """
      Function to place all of the computed data into the output object, (DataObjects)
      @ In, finishedJob, object, JobHandler object that is in charge of running this postprocessor
      @ In, output, object, the object where we want to place our computed results
      @ Out, None
    """
    evaluation = finishedJob.getEvaluation()
    if isinstance(evaluation, Runners.Error):
      self.raiseAnError(RuntimeError, ' No available output to collect (Run probably is not finished yet) via',self.printTag)
    if not set(output.getParaKeys('inputs')) == set(self.variables):
      self.raiseAnError(RuntimeError, ' ETimporter: set of branching variables in the ET ( ' + str(output.getParaKeys('inputs')) + ' ) is not identical to the set of input variables specified in the PointSet (' + str(self.variables) +')')

    outputDict = evaluation[1]
    # Output to file
    if output.type in ['PointSet']:
      for key in output.getParaKeys('inputs'):
        for value in self.outputDict['inputs'][key]:
          output.updateInputValue(str(key),value)
      for key in output.getParaKeys('outputs'):
        for value in self.outputDict['outputs'][key]:
          output.updateOutputValue(str(key),value)
    else:
      self.raiseAWarning('Output type ' + str(output.type) + ' is not supported.')

  def findAllRecursive(self, node, element, result = None):
    """
      A function for recursively traversing a node in an elementTree to find
      all instances of a tag
      @ In, node, ET.Element, the current node to search under
      @ In, element, str, the string name of the tags to locate
      @ InOut, result, list, a list of the currently recovered results
    """
    if result is None:
      result = []
    for item in node.getchildren():
      if item.tag == element:
        result.append(item)
      self.findAllRecursive(item, element, result)
    return result

  def constructPointDFS(self, node, inputMap, stateMap, outputMap, X, rowCounter):
    """
      Construct a "sequence" using a depth-first search on a node, each call
      will be on a fork except in the base case which will be called on a
      sequence node. The recursive case will traverse into a path node, thus
      path nodes will be "skipped" in the call stack as one level of paths
      will be processed per recursive call in order to set one of the columns
      of X for the row identified by rowCounter.
      @ In, node, ET.Element, the current node to process
      @ In, inputMap, list, a map for converting string variable names into
            sequential non-negative integers that can be used to index X
      @ In, stateMap, dict, a map similar to above, but instead converts the
            possible states for each event (variable) into non-negative
            integers
      @ In, outputMap, list, a map for converting string outcome values into
            non-negative integers
      @ In, X, np.array, data object to populate with values
      @ In, rowCounter, int, the row we are currently editing in X
      @ Out, offset, int, the number of rows of X this call has populated
    """

    # Construct point
    if node.tag == 'sequence':
      col = X.shape[1]-1
      outcome = node.get('name')

      val = outputMap[outcome]

      X[rowCounter, col] = val
      rowCounter += 1
    elif node.tag == 'fork':
      event = node.get('functional-event')
      col = inputMap.index(event)

      for path in node.findall('path'):
          state = path.get('state')
          if   state == 'failure':
            val = '+1'
          elif state =='success':
            val = '0'
          else:
            val = stateMap[event].index(state)

          ## Fill in the rest of the data as the recursive nature will only
          ## fill in the details under this branch, later iterations will
          ## correct lower rows if a path does change
          X[rowCounter, col] = val

          for fork in path.getchildren():
              newCounter = self.constructPointDFS(fork, inputMap, stateMap, outputMap, X, rowCounter)
              for i in range(newCounter-rowCounter):
                  X[rowCounter+i, col] = val
              rowCounter = newCounter

    return rowCounter






