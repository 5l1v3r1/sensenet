import sys
sys.path.append('..')
import gym
import sensenet
from sensenet.envs.handroid.hand_env import HandEnv
def test_environments():
    tenv = HandEnv()
    env = gym.make("CartPole-v0")
    input_dim = env.observation_space.shape[0]
    output_dim = env.action_space.n
    tinput_dim = tenv.observation_space.shape[0]
    toutput_dim = tenv.action_space.n
    assert tinput_dim > 0
    print("gym observation space: ",input_dim)
    print("gym action space: ",output_dim)
    print("touch observation space: ",tinput_dim)
    print("touch action space: ",toutput_dim)
    state = env.reset()
    tstate = tenv.reset()
    print("gym state:",state)
    print("touch state:",tstate)
    #state, reward, done, _ = env.step(action[0,0])
