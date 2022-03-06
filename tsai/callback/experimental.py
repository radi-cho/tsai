# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/060_callback.experimental.ipynb (unless otherwise specified).

__all__ = ['GamblersCallback', 'gambler_loss', 'UBDAug', 'BatchLossFilter', 'RandomWeightLossWrapper',
           'SamplerWithReplacement', 'BatchMasker', 'SamplerWithReplacement']

# Cell
import torch.multiprocessing
torch.multiprocessing.set_sharing_strategy('file_system')

# Cell
from fastai.callback.all import *
from ..imports import *
from ..utils import *
from ..data.preprocessing import *
from ..data.transforms import *
from ..models.layers import *
from .MVP import *

# Cell
class GamblersCallback(Callback):
    "A callback to use metrics with gambler's loss"
    def after_loss(self): self.learn.pred = self.learn.pred[..., :-1]


def gambler_loss(reward=2):
    def _gambler_loss(model_output, targets):
        outputs = torch.nn.functional.softmax(model_output, dim=1)
        outputs, reservation = outputs[:, :-1], outputs[:, -1]
        gain = torch.gather(outputs, dim=1, index=targets.unsqueeze(1)).squeeze()
        doubling_rate = (gain + reservation / reward).log()
        return - doubling_rate.mean()
    return

# Cell
class UBDAug(Callback):
    r"""A callback to implement the uncertainty-based data augmentation."""

    def __init__(self, batch_tfms:list, N:int=2, C:int=4, S:int=1):
        r'''
        Args:
            batch_tfms:   list of available transforms applied to the combined batch. They will be applied in addition to the dl tfms.
            N:            # composition steps (# transforms randomly applied to each sample)
            C:            # augmented data per input data (# times N transforms are applied)
            S:            # selected data points used for training (# augmented samples in the final batch from each original sample)
        '''

        self.C, self.S = C, min(S, C)
        self.batch_tfms = L(batch_tfms)
        self.n_tfms = len(self.batch_tfms)
        self.N = min(N, self.n_tfms)

    def before_fit(self):
        assert hasattr(self.loss_func, 'reduction'), "You need to pass a loss_function with a 'reduction' attribute"
        self.red = self.loss_func.reduction

    def before_batch(self):
        if self.training:
            with torch.no_grad():
                setattr(self.loss_func, 'reduction', 'none')
                for i in range(self.C):
                    idxs = np.random.choice(self.n_tfms, self.N, False)
                    x_tfm = compose_tfms(self.x, self.batch_tfms[idxs], split_idx=0)
                    loss = self.loss_func(self.learn.model(x_tfm), self.y).reshape(-1,1)
                    if i == 0:
                        x2 = x_tfm.unsqueeze(1)
                        max_loss = loss
                    else:
                        losses = torch.cat((max_loss, loss), dim=1)
                        x2 = torch.cat((x2, x_tfm.unsqueeze(1)), dim=1)
                        x2 = x2[np.arange(x2.shape[0]).reshape(-1,1), losses.argsort(1)[:, -self.S:]]
                        max_loss = losses.max(1)[0].reshape(-1,1)
                setattr(self.loss_func, 'reduction', self.red)
            x2 = x2.reshape(-1, self.x.shape[-2], self.x.shape[-1])
            if self.S > 1: self.learn.yb = (torch_tile(self.y, 2),)
            self.learn.xb = (x2,)

    def __repr__(self): return f'UBDAug({[get_tfm_name(t) for t in self.batch_tfms]})'

# Cell
class BatchLossFilter(Callback):
    """ Callback that selects the hardest samples in every batch representing a percentage of the total loss"""

    def __init__(self, loss_perc=1., schedule_func:Optional[callable]=None):
        store_attr()

    def before_fit(self):
        self.run = not hasattr(self, "gather_preds")
        if not(self.run): return
        self.crit = self.learn.loss_func
        if hasattr(self.crit, 'reduction'): self.red = self.crit.reduction

    def before_batch(self):
        if not self.training: return
        if self.schedule_func is None: loss_perc = self.loss_perc
        else: loss_perc = self.loss_perc * self.schedule_func(self.pct_train)
        if loss_perc == 1.: return
        with torch.no_grad():
            if hasattr(self.crit, 'reduction'):  setattr(self.crit, 'reduction', 'none')
            losses = self.crit(self.learn.model(self.x), self.y)
            if losses.ndim == 2: losses = losses.mean(-1)
            if hasattr(self.crit, 'reduction'):  setattr(self.crit, 'reduction', self.red)
            losses /= losses.sum()
            idxs = torch.argsort(losses, descending=True)
            cut_idx = max(1, torch.argmax((losses[idxs].cumsum(0) > loss_perc).float()))
            idxs = idxs[:cut_idx]
            self.learn.xb = tuple(xbi[idxs] for xbi in self.learn.xb)
            self.learn.yb = tuple(ybi[idxs] for ybi in self.learn.yb)

    def after_fit(self):
        if hasattr(self.learn.loss_func, 'reduction'):  setattr(self.learn.loss_func, 'reduction', self.red)

# Cell

class RandomWeightLossWrapper(Callback):

    def before_fit(self):
        self.run = not hasattr(self, "gather_preds")
        if not(self.run): return
        self.crit = self.learn.loss_func
        if hasattr(self.crit, 'reduction'): self.red = self.crit.reduction
        self.learn.loss_func = self._random_weight_loss

    def _random_weight_loss(self, input: Tensor, target: Tensor) -> Tensor:
        if self.training:
            setattr(self.crit, 'reduction', 'none')
            loss = self.crit(input, target)
            setattr(self.crit, 'reduction', self.red)
            rw = torch.rand(input.shape[0], device=input.device)
            rw /= rw.sum()
            non_red_loss = loss * rw
            return non_red_loss.sum()
        else:
            return self.crit(input, target)

    def after_fit(self):
        if hasattr(self.crit, 'reduction'): setattr(self.crit, 'reduction', self.red)
        self.learn.loss_func = self.crit

# Cell

class SamplerWithReplacement(Callback):
    """ Callback that selects a percentage of samples and/ or sequence steps with replacement from each training batch"""

    def before_fit(self):
        self.run = not hasattr(self, "gather_preds")
        if not(self.run): return

        self.old_get_idxs = self.learn.dls.train.get_idxs
        self.learn.dls.train.get_idxs = self._get_idxs

    def _get_idxs(self):
        dl = self.learn.dls.train
        if dl.n==0: return []
        if dl.weights is not None:
            return np.random.choice(dl.n, dl.n, p=dl.weights)
        idxs = Inf.count if dl.indexed else Inf.nones
        if dl.n is not None: idxs = np.random.choice(dl.n,dl.n,True)
        if dl.shuffle: idxs = dl.shuffle_fn(idxs)
        return idxs

    def after_fit(self):
        self.learn.dls.train.get_idxs = self.old_get_idxs

# Cell

class BatchMasker(Callback):
    """ Callback that applies a random mask to each sample in a training batch

    Args:
    ====
    r:                  probability of masking.
    subsequence_mask:   apply a mask to random subsequences.
    lm:                 average mask len when using stateful (geometric) masking.
    stateful:           geometric distribution is applied so that average mask length is lm.
    sync:               all variables have the same masking.
    variable_mask:      apply a mask to random variables. Only applicable to multivariate time series.
    future_mask:        used to train a forecasting model.
    schedule_func:      if a scheduler is passed, it will modify the probability of masking during training.
    """

    def __init__(self, r:float=.15, lm:int=3, stateful:bool=True, sync:bool=False, subsequence_mask:bool=True,
                 variable_mask:bool=False, future_mask:bool=False, schedule_func:Optional[callable]=None):
        store_attr()

    def before_fit(self):
        self.run = not hasattr(self, "gather_preds")
        if not(self.run): return

    def before_batch(self):
        if not self.training: return
        r = self.r * self.schedule_func(self.pct_train) if self.schedule_func is not None else self.r
        mask = create_mask(self.x,  r=r, lm=self.lm, stateful=self.stateful, sync=self.sync,
                        subsequence_mask=self.subsequence_mask, variable_mask=self.variable_mask, future_mask=self.future_mask)
        self.learn.xb = (self.xb[0].masked_fill(mask, 0),)
        # In my tests, mask-based compensation doesn't seem to be important. ??
        # mean_per_seq = (torch.max(torch.ones(1, device=mask.device), torch.sum(mask, dim=-1).unsqueeze(-1)) / mask.shape[-1])
        # self.learn.xb = (self.xb[0].masked_fill(mask, 0) / (1 - mean_per_seq), )

# Cell

class SamplerWithReplacement(Callback):
    """ Callback that modify the sampler to select a percentage of samples and/ or sequence steps with replacement from each training batch"""

    def before_fit(self):
        self.run = not hasattr(self, "gather_preds")
        if not(self.run): return

        self.old_get_idxs = self.learn.dls.train.get_idxs
        self.learn.dls.train.get_idxs = self._get_idxs

    def _get_idxs(self):
        dl = self.learn.dls.train
        if dl.n==0: return []
        if dl.weights is not None:
            return np.random.choice(dl.n, dl.n, p=dl.weights)
        idxs = Inf.count if dl.indexed else Inf.nones
        if dl.n is not None: idxs = np.random.choice(dl.n,dl.n,True)
        if dl.shuffle: idxs = dl.shuffle_fn(idxs)
        return idxs

    def after_fit(self):
        self.learn.dls.train.get_idxs = self.old_get_idxs