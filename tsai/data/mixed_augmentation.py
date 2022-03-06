# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/018_data.mixed_augmentation.ipynb (unless otherwise specified).

__all__ = ['MixHandler1d', 'MixUp1d', 'MixUp1D', 'CutMix1d', 'IntraClassCutMix1d']

# Cell
from torch.distributions.beta import Beta
from fastai.callback.core import Callback
from fastai.layers import NoneReduce
from ..imports import *
from ..utils import *
warnings.filterwarnings("ignore", category=UserWarning)

# Cell
def _reduce_loss(loss, reduction='mean'):
    "Reduce the loss based on `reduction`"
    return loss.mean() if reduction == 'mean' else loss.sum() if reduction == 'sum' else loss

# Cell
class MixHandler1d(Callback):
    "A handler class for implementing mixed sample data augmentation"
    run_valid = False

    def __init__(self, alpha=0.5):
        self.distrib = Beta(alpha, alpha)

    def before_train(self):
        self.labeled = self.dls.d
        if self.labeled:
            self.stack_y = getattr(self.learn.loss_func, 'y_int', False)
            if self.stack_y: self.old_lf, self.learn.loss_func = self.learn.loss_func, self.lf

    def after_train(self):
        if self.labeled and self.stack_y: self.learn.loss_func = self.old_lf

    def lf(self, pred, *yb):
        if not self.training: return self.old_lf(pred, *yb)
        with NoneReduce(self.old_lf) as lf: loss = torch.lerp(lf(pred, *self.yb1), lf(pred, *yb), self.lam)
        return _reduce_loss(loss, getattr(self.old_lf, 'reduction', 'mean'))

# Cell
class MixUp1d(MixHandler1d):
    "Implementation of https://arxiv.org/abs/1710.09412"

    def __init__(self, alpha=.4):
        super().__init__(alpha)

    def before_batch(self):
        lam = self.distrib.sample((self.x.size(0), ))
        self.lam = torch.max(lam, 1 - lam).to(self.x.device)
        shuffle = torch.randperm(self.x.size(0))
        xb1 = self.x[shuffle]
        self.learn.xb = L(xb1, self.xb).map_zip(torch.lerp, weight=unsqueeze(self.lam, n=self.x.ndim - 1))
        if self.labeled:
            self.yb1 = tuple((self.y[shuffle], ))
            if not self.stack_y: self.learn.yb = L(self.yb1, self.yb).map_zip(torch.lerp, weight=unsqueeze(self.lam, n=self.y.ndim - 1))

MixUp1D = MixUp1d

# Cell
class CutMix1d(MixHandler1d):
    "Implementation of `https://arxiv.org/abs/1905.04899`"

    def __init__(self, alpha=1.):
        super().__init__(alpha)

    def before_batch(self):
        bs, *_, seq_len = self.x.size()
        self.lam = self.distrib.sample((1, ))
        shuffle = torch.randperm(bs)
        xb1 = self.x[shuffle]
        x1, x2 = self.rand_bbox(seq_len, self.lam)
        self.learn.xb[0][..., x1:x2] = xb1[..., x1:x2]
        self.lam = (1 - (x2 - x1) / float(seq_len)).item()
        if self.labeled:
            self.yb1 = tuple((self.y[shuffle], ))
            if not self.stack_y:
                self.learn.yb = tuple(L(self.yb1, self.yb).map_zip(torch.lerp, weight=unsqueeze(self.lam, n=self.y.ndim - 1)))

    def rand_bbox(self, seq_len, lam):
        cut_seq_len = torch.round(seq_len * (1. - lam)).type(torch.long)
        half_cut_seq_len = torch.div(cut_seq_len, 2, rounding_mode='floor')

        # uniform
        cx = torch.randint(0, seq_len, (1, ))
        x1 = torch.clamp(cx - half_cut_seq_len, 0, seq_len)
        x2 = torch.clamp(cx + half_cut_seq_len, 0, seq_len)
        return x1, x2

# Cell
class IntraClassCutMix1d(Callback):
    "Implementation of CutMix applied to examples of the same class"
    run_valid = False

    def __init__(self, alpha=1.):
        self.distrib = Beta(tensor(alpha), tensor(alpha))

    def before_batch(self):
        bs, *_, seq_len = self.x.size()
        idxs = torch.arange(bs, device=self.x.device)
        y = torch.tensor(self.y)
        unique_c = torch.unique(y).tolist()
        idxs_by_class = torch.cat([idxs[torch.eq(y, c)] for c in unique_c])
        idxs_shuffled_by_class = torch.cat([random_shuffle(idxs[torch.eq(y, c)]) for c in unique_c])
        self.lam = self.distrib.sample((1, ))
        x1, x2 = self.rand_bbox(seq_len, self.lam)
        xb1 = self.x[idxs_shuffled_by_class]
        self.learn.xb[0][idxs_by_class, :, x1:x2] = xb1[..., x1:x2]

    def rand_bbox(self, seq_len, lam):
        cut_seq_len = torch.round(seq_len * (1. - lam)).type(torch.long)
        half_cut_seq_len = torch.div(cut_seq_len, 2, rounding_mode='floor')

        # uniform
        cx = torch.randint(0, seq_len, (1, ))
        x1 = torch.clamp(cx - half_cut_seq_len, 0, seq_len)
        x2 = torch.clamp(cx + half_cut_seq_len, 0, seq_len)
        return x1, x2