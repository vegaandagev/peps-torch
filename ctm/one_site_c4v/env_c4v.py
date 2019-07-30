import torch
from args import CTMARGS, GLOBALARGS
from ipeps import IPEPS

class ENV_C4V(torch.nn.Module):
    def __init__(self, chi, state, ctm_args=CTMARGS(), global_args=GLOBALARGS()):
        r"""
        :param chi: environment bond dimension :math:`\chi`
        :param state: wavefunction
        :param ctm_args: CTM algorithm configuration
        :param global_args: global configuration
        :type chi: int
        :type state: IPEPS
        :type ctm_args: CTMARGS
        :type global_args: GLOBALARGS

        Assuming c4v symmetric single-site ``state`` create corresponding half-row(column) tensor T 
        and corner tensor C. The corner tensor has dimensions :math:`\chi \times \chi`
        and the half-row(column) tensor has dimensions :math:`\chi \times \chi \times D^2`::

            y\x -1 0 1
             -1  C T C
              0  T A T
              1  C T C 
        
        The environment tensors of an ENV object ``e`` are accesed through members ``C`` and ``T`` 
        The index-position convention is as follows: For upper left C and left T start 
        from the index in the **direction "up"** <=> (-1,0) and continue **anti-clockwise**::
        
            C--1 0--T--1 0--C
            |       |       |
            0       2       1
            0               0
            |               |
            T--2         2--T
            |               |
            1               1
            0       2       0
            |       |       |
            C--1 0--T--1 1--C

        All C's and T's in the above diagram are identical and they are symmetric under the exchange of
        environment bond indices :math:`C_{ij}=C_{ji}` and :math:`T_{ija}=C_{jia}`.  
        """
        assert len(state.sites)==1, "Not a 1-site ipeps"
        super(ENV_C4V, self).__init__()
        self.dtype= global_args.dtype
        self.device= global_args.device
        self.chi= chi

        # initialize environment tensors
        # The same structure is preserved as for generic ipeps ``ENV``. We store keys for access
        # to dummy dicts ``C`` and ``T``
        self.keyC= ((0,0),(-1,-1))
        self.keyT= ((0,0),(-1,0))
        self.C= dict()
        self.T= dict()

        self.C[self.keyC]= torch.empty((self.chi,self.chi), dtype=self.dtype, device=self.device)
        site= next(iter(state.sites.values()))
        self.T[self.keyT]= torch.empty((self.chi,self.chi,site.size()[2]*site.size()[2]), \
            dtype=self.dtype, device=self.device)

def init_env(state, env, ctm_args=CTMARGS()):
    """
    :param state: wavefunction
    :param env: C4v symmetric CTM environment
    :param ctm_args: CTM algorithm configuration
    :type state: IPEPS
    :type env: ENV_C4V
    :type ctm_args: CTMARGS

    Initializes the environment `env` according to one of the supported options specified 
    inside `CTMARGS.ctm_env_init_type` [TODO link here]
    
 
    * CONST - C and T tensors have all their elements intialized to a value 1
    * RANDOM - C and T tensors have elements with random numbers drawn from uniform
      distribution [0,1)
    * CTMRG - tensors C and T are built from the on-site tensor of `state` 
    """
    if ctm_args.ctm_env_init_type=='CONST':
        init_const(env, ctm_args.verbosity_initialization)
    elif ctm_args.ctm_env_init_type=='RANDOM':
        init_random(env, ctm_args.verbosity_initialization)
    elif ctm_args.ctm_env_init_type=='CTMRG':
        init_from_ipeps(state, env, ctm_args.verbosity_initialization)
    else:
        raise ValueError("Invalid environment initialization: "+str(ctm_args.ctm_env_init_type))

def init_const(env, verbosity=0):
    for key,t in env.C.items():
        env.C[key]= torch.ones(t.size(), dtype=env.dtype, device=env.device)
    for key,t in env.T.items():
        env.T[key]= torch.ones(t.size(), dtype=env.dtype, device=env.device)

# TODO restrict random corners to have pos-semidef spectrum
def init_random(env, verbosity=0):
    for key,t in env.C.items():
        env.C[key]= torch.rand(t.size(), dtype=env.dtype, device=env.device)
    for key,t in env.T.items():
        env.T[key]= torch.rand(t.size(), dtype=env.dtype, device=env.device)

# TODO handle case when chi < bond_dim^2
def init_from_ipeps(state, env, verbosity=0):
    if verbosity>0:
        print("ENV: init_from_ipeps")

    # Left-upper corner
    #
    #     i      = C--1     
    # j--A--3      0
    #   /\
    #  2  m
    #      \ i
    #    j--A--3
    #      /
    #     2
    A= next(iter(state.sites.values()))
    dimsA= A.size()
    a= torch.einsum('mijef,mijab->eafb',(A,A)).contiguous().view(dimsA[3]**2, dimsA[4]**2)
    env.C[env.keyC]= torch.zeros(env.chi,env.chi, dtype=env.dtype, device=env.device)
    env.C[env.keyC][:dimsA[3]**2,:dimsA[4]**2]=a/torch.max(torch.abs(a))

    # left transfer matrix
    #
    #     0      = 0     
    # i--A--3      T--2
    #   /\         1
    #  2  m
    #      \ 0
    #    i--A--3
    #      /
    #     2
    a = torch.einsum('meifg,maibc->eafbgc',(A,A)).contiguous().view(dimsA[1]**2, dimsA[3]**2, dimsA[4]**2)
    env.T[env.keyT]= torch.zeros((env.chi,env.chi,dimsA[4]**2), dtype=env.dtype, device=env.device)
    env.T[env.keyT][:dimsA[1]**2,:dimsA[3]**2,:]=a/torch.max(torch.abs(a))

def print_env(env, verbosity=0):
    print("dtype "+str(env.dtype))
    print("device "+str(env.device))

    print("C "+str(env.C[keyC].size()))
    if verbosity>0: 
        print(env.C[key])
    
    key= ((0,0),(-1,0))
    print("T "+str(env.T[keyT].size()))
    if verbosity>0:
        print(env.T[key])