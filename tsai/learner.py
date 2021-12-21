# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/052_learner.ipynb (unless otherwise specified).

__all__ = ['load_all', 'load_learner_all', 'get_arch', 'all_archs_names', 'ts_learner', 'tsimage_learner']

# Cell
from .imports import *
from .utils import random_shuffle
from .data.core import *
from .data.validation import *
from .inference import *
from .models.utils import *
from .models.InceptionTimePlus import *
from fastai.learner import *
from fastai.vision.models.all import *
from fastai.data.transforms import *

# Cell
@patch
def show_batch(self:Learner, **kwargs):
    self.dls.show_batch(**kwargs)

# Cell
@patch
def remove_all_cbs(self:Learner, max_iters=10):
    i = 0
    while len(self.cbs) > 0 and i < max_iters:
        self.remove_cbs(self.cbs)
        i += 1
    if len(self.cbs) > 0: print(f'Learner still has {len(self.cbs)} callbacks: {self.cbs}')

# Cell
@patch
def one_batch(self:Learner, i, b): # this fixes a bug that will be managed in the next release of fastai
    self.iter = i
#     b_on_device = tuple( e.to(device=self.dls.device) for e in b if hasattr(e, "to")) if self.dls.device is not None else b
    b_on_device = to_device(b, device=self.dls.device) if self.dls.device is not None else b
    self._split(b_on_device)
    self._with_events(self._do_one_batch, 'batch', CancelBatchException)

# Cell
@patch
def save_all(self:Learner, path='export', dls_fname='dls', model_fname='model', learner_fname='learner', verbose=False):
    path = Path(path)
    if not os.path.exists(path): os.makedirs(path)

    self.dls_type = self.dls.__class__.__name__
    if self.dls_type == "MixedDataLoaders":
        self.n_loaders = (len(self.dls.loaders), len(self.dls.loaders[0].loaders))
        dls_fnames = []
        for i,dl in enumerate(self.dls.loaders):
            for j,l in enumerate(dl.loaders):
                l = l.new(num_workers=1)
                torch.save(l, path/f'{dls_fname}_{i}_{j}.pth')
                dls_fnames.append(f'{dls_fname}_{i}_{j}.pth')
    else:
        dls_fnames = []
        self.n_loaders = len(self.dls.loaders)
        for i,dl in enumerate(self.dls):
            dl = dl.new(num_workers=1)
            torch.save(dl, path/f'{dls_fname}_{i}.pth')
            dls_fnames.append(f'{dls_fname}_{i}.pth')

    # Saves the model along with optimizer
    self.model_dir = path
    self.save(f'{model_fname}', with_opt=True)

    # Export learn without the items and the optimizer state for inference
    self.export(path/f'{learner_fname}.pkl')

    pv(f'Learner saved:', verbose)
    pv(f"path          = '{path}'", verbose)
    pv(f"dls_fname     = '{dls_fnames}'", verbose)
    pv(f"model_fname   = '{model_fname}.pth'", verbose)
    pv(f"learner_fname = '{learner_fname}.pkl'", verbose)


def load_all(path='export', dls_fname='dls', model_fname='model', learner_fname='learner', device=None, pickle_module=pickle, verbose=False):

    if isinstance(device, int): device = torch.device('cuda', device)
    elif device is None: device = default_device()
    if device == 'cpu': cpu = True
    else: cpu = None

    path = Path(path)
    learn = load_learner(path/f'{learner_fname}.pkl', cpu=cpu, pickle_module=pickle_module)
    learn.load(f'{model_fname}', with_opt=True, device=device)


    if learn.dls_type == "MixedDataLoaders":
        dls_fnames = []
        _dls = []
        for i in range(learn.n_loaders[0]):
            _dl = []
            for j in range(learn.n_loaders[1]):
                l = torch.load(path/f'{dls_fname}_{i}_{j}.pth', map_location=device, pickle_module=pickle_module)
                l = l.new(num_workers=0)
                l.to(device)
                dls_fnames.append(f'{dls_fname}_{i}_{j}.pth')
                _dl.append(l)
            _dls.append(MixedDataLoader(*_dl, path=learn.dls.path, device=device, shuffle=l.shuffle))
        learn.dls = MixedDataLoaders(*_dls, path=learn.dls.path, device=device)

    else:
        loaders = []
        dls_fnames = []
        for i in range(learn.n_loaders):
            dl = torch.load(path/f'{dls_fname}_{i}.pth', map_location=device, pickle_module=pickle_module)
            dl = dl.new(num_workers=0)
            dl.to(device)
            first(dl)
            loaders.append(dl)
            dls_fnames.append(f'{dls_fname}_{i}.pth')
        learn.dls = type(learn.dls)(*loaders, path=learn.dls.path, device=device)


    pv(f'Learner loaded:', verbose)
    pv(f"path          = '{path}'", verbose)
    pv(f"dls_fname     = '{dls_fnames}'", verbose)
    pv(f"model_fname   = '{model_fname}.pth'", verbose)
    pv(f"learner_fname = '{learner_fname}.pkl'", verbose)
    return learn

load_learner_all = load_all

# Cell
@patch
@delegates(subplots)
def plot_metrics(self: Recorder, nrows=None, ncols=None, figsize=None, final_losses=True, perc=.5, **kwargs):
    n_values = len(self.recorder.values)
    if n_values < 2:
        print('not enough values to plot a chart')
        return
    metrics = np.stack(self.values)
    n_metrics = metrics.shape[1]
    names = self.metric_names[1:n_metrics+1]
    if final_losses:
        sel_idxs = int(round(n_values * perc))
        if sel_idxs >= 2:
            metrics = np.concatenate((metrics[:,:2], metrics), -1)
            names = names[:2] + names
        else:
            final_losses = False
    n = len(names) - 1 - final_losses
    if nrows is None and ncols is None:
        nrows = int(math.sqrt(n))
        ncols = int(np.ceil(n / nrows))
    elif nrows is None: nrows = int(np.ceil(n / ncols))
    elif ncols is None: ncols = int(np.ceil(n / nrows))
    figsize = figsize or (ncols * 6, nrows * 4)
    fig, axs = subplots(nrows, ncols, figsize=figsize, **kwargs)
    axs = [ax if i < n else ax.set_axis_off() for i, ax in enumerate(axs.flatten())][:n]
    axs = ([axs[0]]*2 + [axs[1]]*2 + axs[2:]) if final_losses else ([axs[0]]*2 + axs[1:])
    for i, (name, ax) in enumerate(zip(names, axs)):
        if i in [0, 1]:
            ax.plot(metrics[:, i], color='#1f77b4' if i == 0 else '#ff7f0e', label='valid' if i == 1 else 'train')
            ax.set_title('losses')
            ax.set_xlim(0, len(metrics)-1)
        elif i in [2, 3] and final_losses:
            ax.plot(np.arange(len(metrics) - sel_idxs, len(metrics)), metrics[-sel_idxs:, i],
                    color='#1f77b4' if i == 2 else '#ff7f0e', label='valid' if i == 3 else 'train')
            ax.set_title('final losses')
            ax.set_xlim(len(metrics) - sel_idxs, len(metrics)-1)
            # ax.set_xticks(np.arange(len(metrics) - sel_idxs, len(metrics)))
        else:
            ax.plot(metrics[:, i], color='#1f77b4' if i == 0 else '#ff7f0e', label='valid' if i > 0 else 'train')
            ax.set_title(name if i >= 2 * (1 + final_losses) else 'losses')
            ax.set_xlim(0, len(metrics)-1)
        ax.legend(loc='best')
        ax.grid(color='gainsboro', linewidth=.5)
    plt.show()


@patch
@delegates(subplots)
def plot_metrics(self: Learner, **kwargs):
    self.recorder.plot_metrics(**kwargs)

# Cell
@patch
@delegates(subplots)
def show_probas(self:Learner, figsize=(6,6), ds_idx=1, dl=None, one_batch=False, max_n=None, **kwargs):
    recorder = copy(self.recorder) # This is to avoid loss of recorded values while generating preds
    if one_batch: dl = self.dls.one_batch()
    probas, targets = self.get_preds(ds_idx=ds_idx, dl=[dl] if dl is not None else None)
    if probas.ndim == 2 and probas.min() < 0 or probas.max() > 1: probas = nn.Softmax(-1)(probas)
    if not isinstance(targets[0].item(), Integral): return
    targets = targets.flatten()
    if max_n is not None:
        idxs = np.random.choice(len(probas), max_n, False)
        probas, targets = probas[idxs], targets[idxs]
    if isinstance(probas, torch.Tensor): probas = probas.detach().cpu().numpy()
    if isinstance(targets, torch.Tensor): targets = targets.detach().cpu().numpy()
    fig = plt.figure(figsize=figsize, **kwargs)
    classes = np.unique(targets)
    nclasses = len(classes)
    vals = np.linspace(.5, .5 + nclasses - 1, nclasses)[::-1]
    plt.vlines(.5, min(vals) - 1, max(vals), color='black', linewidth=.5)
    cm = plt.get_cmap('gist_rainbow')
    color = [cm(1.* c/nclasses) for c in range(1, nclasses + 1)][::-1]
    # class_probas = np.array([probas[i,t] for i,t in enumerate(targets)])
    class_probas = np.array([probas[i][t] for i,t in enumerate(targets)])
    for i, c in enumerate(classes):
        plt.scatter(class_probas[targets == c] if nclasses > 2 or i > 0 else 1 - class_probas[targets == c],
                    targets[targets == c] + .5 * (np.random.rand((targets == c).sum()) - .5), color=color[i], edgecolor='black', alpha=.2, s=100)
        if nclasses > 2: plt.vlines((targets == c).mean(), i - .5, i + .5, color='r', linewidth=.5)
    plt.hlines(vals, 0, 1)
    plt.ylim(min(vals) - 1, max(vals))
    plt.xlim(0,1)
    plt.xticks(np.linspace(0,1,11), fontsize=12)
    plt.yticks(classes, [self.dls.vocab[x] for x in classes], fontsize=12)
    plt.title('Predicted proba per true class' if nclasses > 2 else 'Predicted class 1 proba per true class', fontsize=14)
    plt.xlabel('Probability', fontsize=12)
    plt.ylabel('True class', fontsize=12)
    plt.grid(axis='x', color='gainsboro', linewidth=.2)
    plt.show()
    self.recorder = recorder

# Cell
all_archs_names = ['FCN', 'FCNPlus', 'InceptionTime', 'InceptionTimePlus', 'InCoordTime', 'XCoordTime', 'InceptionTimePlus17x17', 'InceptionTimePlus32x32',
                   'InceptionTimePlus47x47', 'InceptionTimePlus62x62', 'InceptionTimeXLPlus', 'MultiInceptionTimePlus', 'MiniRocketClassifier',
                   'MiniRocketRegressor', 'MiniRocketVotingClassifier', 'MiniRocketVotingRegressor', 'MiniRocketFeaturesPlus', 'MiniRocketPlus',
                   'MiniRocketHead', 'InceptionRocketFeaturesPlus', 'InceptionRocketPlus', 'MLP', 'MultiInputNet', 'OmniScaleCNN', 'RNN', 'LSTM', 'GRU',
                   'RNNPlus', 'LSTMPlus', 'GRUPlus', 'RNN_FCN', 'LSTM_FCN', 'GRU_FCN', 'MRNN_FCN', 'MLSTM_FCN', 'MGRU_FCN', 'ROCKET', 'RocketClassifier',
                   'RocketRegressor', 'ResCNN', 'ResNet', 'ResNetPlus', 'TCN', 'TSPerceiver', 'TST', 'TSTPlus', 'MultiTSTPlus', 'TSiTPlus', 'TSiTPlus',
                   'TabFusionTransformer', 'TSTabFusionTransformer', 'TabModel', 'TabTransformer', 'TransformerModel', 'XCM', 'XCMPlus', 'xresnet1d18',
                   'xresnet1d34', 'xresnet1d50', 'xresnet1d101', 'xresnet1d152', 'xresnet1d18_deep', 'xresnet1d34_deep', 'xresnet1d50_deep',
                   'xresnet1d18_deeper', 'xresnet1d34_deeper', 'xresnet1d50_deeper', 'XResNet1dPlus', 'xresnet1d18plus', 'xresnet1d34plus',
                   'xresnet1d50plus', 'xresnet1d101plus', 'xresnet1d152plus', 'xresnet1d18_deepplus', 'xresnet1d34_deepplus', 'xresnet1d50_deepplus',
                   'xresnet1d18_deeperplus', 'xresnet1d34_deeperplus', 'xresnet1d50_deeperplus', 'XceptionTime', 'XceptionTimePlus', 'mWDN']


def get_arch(arch_name):
    if arch_name == "FCN":
        from .models.FCN import FCN
        arch = FCN
    elif arch_name == "FCNPlus":
        from .models.FCNPlus import FCNPlus
        arch = FCNPlus
    elif arch_name == "InceptionTime":
        from .models.InceptionTime import InceptionTime
        arch = InceptionTime
    elif arch_name == "InceptionTimePlus":
        from .models.InceptionTimePlus import InceptionTimePlus
        arch = InceptionTimePlus
    elif arch_name == "InCoordTime":
        from .models.InceptionTimePlus import InCoordTime
        arch = InCoordTime
    elif arch_name == "XCoordTime":
        from .models.InceptionTimePlus import XCoordTime
        arch = XCoordTime
    elif arch_name == "InceptionTimePlus17x17":
        from .models.InceptionTimePlus import InceptionTimePlus17x17
        arch = InceptionTimePlus17x17
    elif arch_name == "InceptionTimePlus32x32":
        from .models.InceptionTimePlus import InceptionTimePlus32x32
        arch = InceptionTimePlus32x32
    elif arch_name == "InceptionTimePlus47x47":
        from .models.InceptionTimePlus import InceptionTimePlus47x47
        arch = InceptionTimePlus47x47
    elif arch_name == "InceptionTimePlus62x62":
        from .models.InceptionTimePlus import InceptionTimePlus62x62
        arch = InceptionTimePlus62x62
    elif arch_name == "InceptionTimeXLPlus":
        from .models.InceptionTimePlus import InceptionTimeXLPlus
        arch = InceptionTimeXLPlus
    elif arch_name == "MultiInceptionTimePlus":
        from .models.InceptionTimePlus import MultiInceptionTimePlus
        arch = MultiInceptionTimePlus
    elif arch_name == "MiniRocketClassifier":
        from .models.MINIROCKET import MiniRocketClassifier
        arch = MiniRocketClassifier
    elif arch_name == "MiniRocketRegressor":
        from .models.MINIROCKET import MiniRocketRegressor
        arch = MiniRocketRegressor
    elif arch_name == "MiniRocketVotingClassifier":
        from .models.MINIROCKET import MiniRocketVotingClassifier
        arch = MiniRocketVotingClassifier
    elif arch_name == "MiniRocketVotingRegressor":
        from .models.MINIROCKET import MiniRocketVotingRegressor
        arch = MiniRocketVotingRegressor
    elif arch_name == "MiniRocketFeaturesPlus":
        from .models.MINIROCKETPlus_Pytorch import MiniRocketFeaturesPlus
        arch = MiniRocketFeaturesPlus
    elif arch_name == "MiniRocketPlus":
        from .models.MINIROCKETPlus_Pytorch import MiniRocketPlus
        arch = MiniRocketPlus
    elif arch_name == "MiniRocketHead":
        from .models.MINIROCKETPlus_Pytorch import MiniRocketHead
        arch = MiniRocketHead
    elif arch_name == "InceptionRocketFeaturesPlus":
        from .models.MINIROCKETPlus_Pytorch import InceptionRocketFeaturesPlus
        arch = InceptionRocketFeaturesPlus
    elif arch_name == "InceptionRocketPlus":
        from .models.MINIROCKETPlus_Pytorch import InceptionRocketPlus
        arch = InceptionRocketPlus
    elif arch_name == "MLP":
        from .models.MLP import MLP
        arch = MLP
    elif arch_name == "MultiInputNet":
        from .models.MultiInputNet import MultiInputNet
        arch = MultiInputNet
    elif arch_name == "OmniScaleCNN":
        from .models.OmniScaleCNN import OmniScaleCNN
        arch = OmniScaleCNN
    elif arch_name == "RNN":
        from .models.RNN import RNN
        arch = RNN
    elif arch_name == "LSTM":
        from .models.RNN import LSTM
        arch = LSTM
    elif arch_name == "GRU":
        from .models.RNN import GRU
        arch = GRU
    elif arch_name == "RNNPlus":
        from .models.RNNPlus import RNNPlus
        arch = RNNPlus
    elif arch_name == "LSTMPlus":
        from .models.RNNPlus import LSTMPlus
        arch = LSTMPlus
    elif arch_name == "GRUPlus":
        from .models.RNNPlus import GRUPlus
        arch = GRUPlus
    elif arch_name == "RNN_FCN":
        from .models.RNN_FCN import RNN_FCN
        arch = RNN_FCN
    elif arch_name == "LSTM_FCN":
        from .models.RNN_FCN import LSTM_FCN
        arch = LSTM_FCN
    elif arch_name == "GRU_FCN":
        from .models.RNN_FCN import GRU_FCN
        arch = GRU_FCN
    elif arch_name == "MRNN_FCN":
        from .models.RNN_FCN import MRNN_FCN
        arch = MRNN_FCN
    elif arch_name == "MLSTM_FCN":
        from .models.RNN_FCN import MLSTM_FCN
        arch = MLSTM_FCN
    elif arch_name == "MGRU_FCN":
        from .models.RNN_FCN import MGRU_FCN
        arch = MGRU_FCN
    elif arch_name == "RNN_FCNPlus":
        from .models.RNN_FCNPlus import RNN_FCNPlus
        arch = RNN_FCNPlus
    elif arch_name == "LSTM_FCNPlus":
        from .models.RNN_FCNPlus import LSTM_FCNPlus
        arch = LSTM_FCNPlus
    elif arch_name == "GRU_FCNPlus":
        from .models.RNN_FCNPlus import GRU_FCNPlus
        arch = GRU_FCNPlus
    elif arch_name == "MRNN_FCNPlus":
        from .models.RNN_FCNPlus import MRNN_FCNPlus
        arch = MRNN_FCNPlus
    elif arch_name == "MLSTM_FCNPlus":
        from .models.RNN_FCNPlus import MLSTM_FCNPlus
        arch = MLSTM_FCNPlus
    elif arch_name == "MGRU_FCNPlus":
        from .models.RNN_FCNPlus import MGRU_FCNPlus
        arch = MGRU_FCNPlus
    elif arch_name == "ROCKET":
        from .models.ROCKET import ROCKET
        arch = ROCKET
    elif arch_name == "RocketClassifier":
        from .models.ROCKET import RocketClassifier
        arch = RocketClassifier
    elif arch_name == "RocketRegressor":
        from .models.ROCKET import RocketRegressor
        arch = RocketRegressor
    elif arch_name == "ResCNN":
        from .models.ResCNN import ResCNN
        arch = ResCNN
    elif arch_name == "ResNet":
        from .models.ResNet import ResNet
        arch = ResNet
    elif arch_name == "ResNetPlus":
        from .models.ResNetPlus import ResNetPlus
        arch = ResNetPlus
    elif arch_name == "TCN":
        from .models.TCN import TCN
        arch = TCN
    elif arch_name == "TSPerceiver":
        from .models.TSPerceiver import TSPerceiver
        arch = TSPerceiver
    elif arch_name == "TST":
        from .models.TST import TST
        arch = TST
    elif arch_name == "TSTPlus":
        from .models.TSTPlus import TSTPlus
        arch = TSTPlus
    elif arch_name == "MultiTSTPlus":
        from .models.TSTPlus import MultiTSTPlus
        arch = MultiTSTPlus
    elif arch_name == "TSiT":
        from .models.TSiTPlus import TSiT
        arch = TSiT
    elif arch_name == "TSiTPlus":
        from .models.TSiTPlus import TSiTPlus
        arch = TSiTPlus
    elif arch_name == "TabFusionTransformer":
        from .models.TabFusionTransformer import TabFusionTransformer
        arch = TabFusionTransformer
    elif arch_name == "TSTabFusionTransformer":
        from .models.TabFusionTransformer import TSTabFusionTransformer
        arch = TSTabFusionTransformer
    elif arch_name == "TabModel":
        from .models.TabModel import TabModel
        arch = TabModel
    elif arch_name == "TabTransformer":
        from .models.TabTransformer import TabTransformer
        arch = TabTransformer
    elif arch_name == "TransformerModel":
        from .models.TransformerModel import TransformerModel
        arch = TransformerModel
    elif arch_name == "XCM":
        from .models.XCM import XCM
        arch = XCM
    elif arch_name == "XCMPlus":
        from .models.XCMPlus import XCMPlus
        arch = XCMPlus
    elif arch_name == "XResNet1d":
        from .models.XResNet1d import XResNet1d
        arch = XResNet1d
    elif arch_name == "xresnet1d18":
        from .models.XResNet1d import xresnet1d18
        arch = xresnet1d18
    elif arch_name == "xresnet1d34":
        from .models.XResNet1d import xresnet1d34
        arch = xresnet1d34
    elif arch_name == "xresnet1d50":
        from .models.XResNet1d import xresnet1d50
        arch = xresnet1d50
    elif arch_name == "xresnet1d101":
        from .models.XResNet1d import xresnet1d101
        arch = xresnet1d101
    elif arch_name == "xresnet1d152":
        from .models.XResNet1d import xresnet1d152
        arch = xresnet1d152
    elif arch_name == "xresnet1d18_deep":
        from .models.XResNet1d import xresnet1d18_deep
        arch = xresnet1d18_deep
    elif arch_name == "xresnet1d34_deep":
        from .models.XResNet1d import xresnet1d34_deep
        arch = xresnet1d34_deep
    elif arch_name == "xresnet1d50_deep":
        from .models.XResNet1d import xresnet1d50_deep
        arch = xresnet1d50_deep
    elif arch_name == "xresnet1d18_deeper":
        from .models.XResNet1d import xresnet1d18_deeper
        arch = xresnet1d18_deeper
    elif arch_name == "xresnet1d34_deeper":
        from .models.XResNet1d import xresnet1d34_deeper
        arch = xresnet1d34_deeper
    elif arch_name == "xresnet1d50_deeper":
        from .models.XResNet1d import xresnet1d50_deeper
        arch = xresnet1d50_deeper
    elif arch_name == "XResNet1dPlus":
        from .models.XResNet1dPlus import XResNet1dPlus
        arch = XResNet1dPlus
    elif arch_name == "xresnet1d18plus":
        from .models.XResNet1dPlus import xresnet1d18plus
        arch = xresnet1d18plus
    elif arch_name == "xresnet1d34plus":
        from .models.XResNet1dPlus import xresnet1d34plus
        arch = xresnet1d34plus
    elif arch_name == "xresnet1d50plus":
        from .models.XResNet1dPlus import xresnet1d50plus
        arch = xresnet1d50plus
    elif arch_name == "xresnet1d101plus":
        from .models.XResNet1dPlus import xresnet1d101plus
        arch = xresnet1d101plus
    elif arch_name == "xresnet1d152plus":
        from .models.XResNet1dPlus import xresnet1d152plus
        arch = xresnet1d152plus
    elif arch_name == "xresnet1d18_deepplus":
        from .models.XResNet1dPlus import xresnet1d18_deepplus
        arch = xresnet1d18_deepplus
    elif arch_name == "xresnet1d34_deepplus":
        from .models.XResNet1dPlus import xresnet1d34_deepplus
        arch = xresnet1d34_deepplus
    elif arch_name == "xresnet1d50_deepplus":
        from .models.XResNet1dPlus import xresnet1d50_deepplus
        arch = xresnet1d50_deepplus
    elif arch_name == "xresnet1d18_deeperplus":
        from .models.XResNet1dPlus import xresnet1d18_deeperplus
        arch = xresnet1d18_deeperplus
    elif arch_name == "xresnet1d34_deeperplus":
        from .models.XResNet1dPlus import xresnet1d34_deeperplus
        arch = xresnet1d34_deeperplus
    elif arch_name == "xresnet1d50_deeperplus":
        from .models.XResNet1dPlus import xresnet1d50_deeperplus
        arch = xresnet1d50_deeperplus
    elif arch_name == "XceptionTime":
        from .models.XceptionTime import XceptionTime
        arch = XceptionTime
    elif arch_name == "XceptionTimePlus":
        from .models.XceptionTimePlus import XceptionTimePlus
        arch = XceptionTimePlus
    elif arch_name == "mWDN":
        from .models.mWDN import mWDN
        arch = mWDN
    else: print(f"please, confirm the name of the architecture ({arch_name})")
    assert arch.__name__ == arch_name
    return arch

# Cell
@delegates(build_ts_model)
def ts_learner(dls, arch=None, c_in=None, c_out=None, seq_len=None, d=None, splitter=trainable_params,
               # learner args
               loss_func=None, opt_func=Adam, lr=defaults.lr, cbs=None, metrics=None, path=None,
               model_dir='models', wd=None, wd_bn_bias=False, train_bn=True, moms=(0.95,0.85,0.95),
               # other model args
               **kwargs):

    if arch is None: arch = InceptionTimePlus
    elif isinstance(arch, str): arch = get_arch(arch)
    model = build_ts_model(arch, dls=dls, c_in=c_in, c_out=c_out, seq_len=seq_len, d=d, **kwargs)
    if hasattr(model, "backbone") and hasattr(model, "head"):
        splitter = ts_splitter
    if loss_func is None:
        if hasattr(dls, 'loss_func'): loss_func = dls.loss_func
        elif hasattr(dls, 'train_ds') and hasattr(dls.train_ds, 'loss_func'): loss_func = dls.train_ds.loss_func
        elif hasattr(dls, 'cat') and not dls.cat: loss_func = MSELossFlat()

    learn = Learner(dls=dls, model=model,
                    loss_func=loss_func, opt_func=opt_func, lr=lr, cbs=cbs, metrics=metrics, path=path, splitter=splitter,
                    model_dir=model_dir, wd=wd, wd_bn_bias=wd_bn_bias, train_bn=train_bn, moms=moms, )

    # keep track of args for loggers
    store_attr('arch', self=learn)

    return learn

# Cell
@delegates(build_tsimage_model)
def tsimage_learner(dls, arch=None, pretrained=False,
               # learner args
               loss_func=None, opt_func=Adam, lr=defaults.lr, cbs=None, metrics=None, path=None,
               model_dir='models', wd=None, wd_bn_bias=False, train_bn=True, moms=(0.95,0.85,0.95),
               # other model args
               **kwargs):

    if arch is None: arch = xresnet34
    elif isinstance(arch, str): arch = get_arch(arch)
    model = build_tsimage_model(arch, dls=dls, pretrained=pretrained, **kwargs)
    learn = Learner(dls=dls, model=model,
                    loss_func=loss_func, opt_func=opt_func, lr=lr, cbs=cbs, metrics=metrics, path=path,
                    model_dir=model_dir, wd=wd, wd_bn_bias=wd_bn_bias, train_bn=train_bn, moms=moms)

    # keep track of args for loggers
    store_attr('arch', self=learn)

    return learn

# Cell
@patch
def decoder(self:Learner, o): return L([self.dls.decodes(oi) for oi in o])

# Cell
@patch
def feature_importance(self:Learner, X=None, y=None, partial_n=None, feature_names=None, key_metric_idx=0, show_chart=True, save_df_path=False,
                       random_state=23):
    r"""Calculates feature importance defined to be the change in a model validation loss or metric when a single feature value is randomly shuffled

    This procedure breaks the relationship between the feature and the target, thus the change in the model validation loss or metric is indicative of
    how much the model depends on the feature.

    Args:
        X: array-like object  containing the time series data for which importance will be measured. If None, all data in the validation set will be used.
        y: array-like object containing the targets. If None, all targets in the validation set will be used.
        partial_n: number of samples (if int) or percent of the validation set (if float) that will be used to measure feature importance. If None,
                   all data will be used.
        feature_names (Optional[list(str)]): list of feature names that will be displayed if available. Otherwise they will be var_0, var_1, etc.
        key_metric_idx (Optional[int]): integer to select the metric used in the calculation. If None or no metric is available,
                                        the change is calculated using the validation loss.
        show_chart (bool): flag to indicate if a chart showing permutation feature importance will be plotted.
        save_df_path (str): path to saved dataframe containing the permutation feature importance results.
        random_state (int): controls the shuffling applied to the data. Pass an int for reproducible output across multiple function calls.
    """

    if X is None:
        X = self.dls.valid.dataset.tls[0].items
    if y is None:
        y = self.dls.valid.dataset.tls[1].items
    if partial_n is not None:
        if isinstance(partial_n, float):
            partial_n = int(round(partial_n * len(X)))
        rand_idxs = random_shuffle(np.arange(len(X)), random_state=random_state)[:partial_n]
        X = X[rand_idxs]
        y = y[rand_idxs]

    metrics = [mn for mn in self.recorder.metric_names if mn not in ['epoch', 'train_loss', 'valid_loss', 'time']]
    if len(metrics) == 0 or key_metric_idx is None:
        metric_name = self.loss_func.__class__.__name__
        key_metric_idx = None
    else:
        metric_name = metrics[key_metric_idx]
        metric = self.recorder.metrics[key_metric_idx].func
    print(f'Selected metric: {metric_name}')

    # Adapted from https://www.kaggle.com/cdeotte/lstm-feature-importance by Chris Deotte (Kaggle GrandMaster)
    if feature_names is None:
        feature_names = [f"var_{i}" for i in range(X.shape[1])]
    else:
        feature_names = listify(feature_names)
    assert len(feature_names) == X.shape[1]

    results = []
    print('Computing feature importance...')

    COLS = ['BASELINE'] + list(feature_names)
    try:
        for k in progress_bar(range(len(COLS))):
            if k>0:
                save_feat = X[:, k-1].copy()
                X[:, k-1] = random_shuffle(X[:, k-1].flatten(), random_state=random_state).reshape(X[:, k-1].shape)
            if key_metric_idx is None:
                value = self.get_X_preds(X, y, with_loss=True)[-1].mean().item()
            else:
                output = self.get_X_preds(X, y)
                value = metric(output[0], output[1]).item()
            print(f"{k:3} feature: {COLS[k]:20} {metric_name}: {value:8.6f}")
            results.append([COLS[k], value])
            del output, value;gc.collect()
            if k>0:
                X[:, k-1] = save_feat
                del save_feat; gc.collect()


    except KeyboardInterrupt:
        if k>0:
            X[:, k-1] = save_feat
            del save_feat; gc.collect()

    # Display feature importance
    if show_chart:
        print()
        df = pd.DataFrame(results, columns=["Feature", metric_name])
        df = df.sort_values(metric_name, ascending=key_metric_idx is None)
        plt.figure(figsize=(10, .5*len(results)))
        plt.barh(np.arange(len(results)), df[metric_name], color="darkblue")
        plt.yticks(np.arange(len(results)), df["Feature"].values)
        plt.title('Permutation Feature Importance', size=16)
        plt.xlabel(f"{metric_name}")
        plt.ylim((-1,len(results)))
        plt.show()

    # Save feature importance
    if save_df_path:
        df = df.sort_values(metric_name,ascending=False)
        df.to_csv(f'{save_df_path}.csv', index=False)