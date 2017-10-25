import time,os,math,inspect,re
import random,argparse
from env import TouchEnv
from torch.autograd import Variable
import numpy as np
from itertools import count
from collections import namedtuple

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torch.autograd as autograd
from torch.autograd import Variable

SavedAction = namedtuple('SavedAction', ['action', 'value'])
class Policy(nn.Module):
  def __init__(self,observation_space_n,action_space_n):
    super(Policy, self).__init__()
    self.affine1 = nn.Linear(observation_space_n, 256)
    self.action1 = nn.Linear(256, 128)
    self.value1 = nn.Linear(256, 128)
    self.action_head = nn.Linear(128, action_space_n)
    self.value_head = nn.Linear(128, 1)
    self.saved_actions = []
    self.rewards = []
    self.init_weights()

  def init_weights(self):
    self.affine1.weight.data.uniform_(-0.1, 0.1)
    self.action1.weight.data.uniform_(-0.1, 0.1)
    self.value1.weight.data.uniform_(-0.1, 0.1)

  def forward(self, x):
    x = F.relu(self.affine1(x))
    xa = F.relu(self.action1(x))
    xv = F.relu(self.value1(x))
    action_scores = self.action_head(xa)
    state_values = self.value_head(xv)
    return F.softmax(action_scores), state_values

class CNN(nn.Module):
  def __init__(self,classification_n):
    super(CNN, self).__init__()
    self.layer1 = nn.Sequential(
      nn.Conv2d(1, 16, kernel_size=5, padding=2),
      nn.BatchNorm2d(16),
      nn.ReLU(),
      nn.MaxPool2d(2))
    self.layer2 = nn.Sequential(
      nn.Conv2d(16, 32, kernel_size=5, padding=2),
      nn.BatchNorm2d(32),
      nn.ReLU(),
      nn.MaxPool2d(2))
    #self.fc = nn.Linear(7*7*32, 2)
    self.fc = nn.Linear(80000, classification_n)
      
  def forward(self, x):
    x = x.unsqueeze(1).float()
    #print("size",x.size())
    out = self.layer1(x)
    out = self.layer2(out)
    #print("size before",out.size())
    out = out.view(out.size(0), -1)
    #print("size after",out.size())
    out = self.fc(out)
    return out

parser = argparse.ArgumentParser(description='TouchNet actor-critic example')
parser.add_argument('--gamma', type=float, default=0.99, metavar='G', help='discount factor (default: 0.99)')
parser.add_argument('--epsilon', type=float, default=0.6, metavar='G', help='epsilon value for random action (default: 0.6)')
parser.add_argument('--seed', type=int, default=42, metavar='N', help='random seed (default: 42)')
parser.add_argument('--batch_size', type=int, default=42, metavar='N', help='batch size (default: 42)')
parser.add_argument('--log-interval', type=int, default=10, metavar='N', help='interval between training status logs (default: 10)') 
parser.add_argument('--render', action='store_true', help='render the environment')
parser.add_argument('--gpu', action='store_true', help='use GPU')
parser.add_argument('--model_path', type=str, help='path to store/retrieve model at')
parser.add_argument('--mode', type=str, default="train", help='train/test/all model')
args = parser.parse_args()


def select_action(state,n_actions,epsilon=0.6):
  if np.random.rand() < epsilon:
    return np.random.choice(n_actions)
  else:
    state = torch.from_numpy(state).float().unsqueeze(0)
    probs, state_value = model(Variable(state))
    action = probs.multinomial()
    model.saved_actions.append(SavedAction(action, state_value))
    return action.data[0][0]

def finish_episode():
  R = 0
  saved_actions = model.saved_actions
  value_loss = 0
  rewards = []
  for r in model.rewards[::-1]:
    R = r + args.gamma * R
    rewards.insert(0, R)
  rewards = torch.Tensor(rewards)
  rewards = (rewards - rewards.mean()) / (rewards.std() + np.finfo(np.float32).eps)
  for (action, value), r in zip(saved_actions, rewards):
    reward = r - value.data[0,0]
    action.reinforce(reward)
    value_loss += F.smooth_l1_loss(value, Variable(torch.Tensor([r])))
  optimizer.zero_grad()
  final_nodes = [value_loss] + list(map(lambda p: p.action, saved_actions))
  gradients = [torch.ones(1)] + [None] * len(saved_actions)
  autograd.backward(final_nodes, gradients)
  optimizer.step()
  del model.rewards[:]
  del model.saved_actions[:]

#train
env = TouchEnv(args)
print("action space: ",env.action_space())
model = Policy(env.observation_space(),env.action_space_n())
cnn = CNN(env.classification_n())
if args.gpu and torch.cuda.is_available():
  model.cuda()
  cnn.cuda()
#if args.model_path and os.path.exists(args.model_path):
#  model.load_state_dict(torch.load(args.model_path))

criterion = nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

classifier_criterion = nn.CrossEntropyLoss()
classifier_optimizer = torch.optim.Adam(cnn.parameters(), lr=0.001)

running_reward = 10
batch = []
labels = []
if args.mode == "train" or args.mode == "all":
  for i_episode in count(1):
    observation = env.reset()
    print("episode: ", i_episode)
    for t in range(1000):
      action = select_action(observation,env.action_space_n(),args.epsilon)
      observation, reward, done, info = env.step(action)
      model.rewards.append(reward)
      
      if np.amax(observation) > 0:  #touching!
        print("touching!")
        if len(batch) > args.batch_size:
          #TODO GPU support
          #batch = torch.from_numpy(np.asarray(batch))
          batch = torch.LongTensor(torch.from_numpy(np.asarray(batch)))
          labels = torch.from_numpy(np.asarray(labels))
          #labels = torch.LongTensor(torch.from_numpy(np.asarray(labels)))
          if args.gpu and torch.cuda.is_available():
            batch = batch.cuda()
            labels = labels.cuda()
          batch = Variable(batch)
          labels = Variable(labels)
          classifier_optimizer.zero_grad()
          outputs = cnn(batch)
          loss = classifier_criterion(outputs, labels)
          loss.backward()
          classifier_optimizer.step()
          print ('Loss: %.4f' %(loss.data[0]))
          batch = []
          labels = []
        else:
          batch.append(observation.reshape(200,200))
          labels.append(env.class_label)
      if done:
        break
    running_reward = running_reward * 0.99 + t * 0.01
    finish_episode()

    if i_episode % args.log_interval == 0:
      print('Episode {}\tLast length: {:5d}\tAverage length: {:.2f}'.format(i_episode, t, running_reward))
    if running_reward > 5000: #env.spec.reward_threshold:
      print("Solved! Running reward is now {} and the last episode runs to {} time steps!".format(running_reward, t))
      break
    if args.model_path:
      torch.save(model.state_dict(), os.path.join(args.model_path, 'policy.pkl' ))
      torch.save(model.state_dict(), os.path.join(args.model_path, 'cnn.pkl' ))
elif args.mode == "test" or args.mode == "all":
  #test
  for i_episode in range(10):
    print("testing on a new object")
    observation = env.reset()
    for t in range(500):
      action = random.sample(env.action_space(),1)[0]
      observation, reward, done, info = env.step(action)
    print("guessing object type","foo")
