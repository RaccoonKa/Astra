import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class ArcMarginProduct(nn.Module):
    def __init__(self, in_features=192, out_features=7, s=30.0, m=0.35, easy_margin=False):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.s = s
        self.m = m
        self.weight = nn.Parameter(torch.FloatTensor(out_features, in_features))
        nn.init.xavier_uniform_(self.weight)

        self.easy_margin = easy_margin
        self.cos_m = math.cos(m)
        self.sin_m = math.sin(m)
        self.th = math.cos(math.pi - m)
        self.mm = math.sin(math.pi - m) * m

    def forward(self, input_tensor, label):
        cosine = F.linear(F.normalize(input_tensor), F.normalize(self.weight))
        sine = torch.sqrt(torch.clamp(1.0 - torch.pow(cosine, 2), min=1e-7))
        phi = cosine * self.cos_m - sine * self.sin_m

        if self.easy_margin:
            phi = torch.where(cosine > 0, phi, cosine)
        else:
            phi = torch.where(cosine > self.th, phi, cosine - self.mm)

        one_hot = torch.zeros(cosine.size(), device=input_tensor.device)
        one_hot.scatter_(1, label.view(-1, 1).long(), 1)

        output = (one_hot * phi) + ((1.0 - one_hot) * cosine)
        output *= self.s
        return output


class DistillationLoss(nn.Module):
    def __init__(self, alpha=0.3):
        super().__init__()
        self.alpha = alpha
        self.ce = nn.CrossEntropyLoss()
        self.cosine = nn.CosineSimilarity(dim=-1)

    def forward(self, student_logits, student_emb, teacher_emb, labels):
        loss_cls = self.ce(student_logits, labels)
        loss_distill = 1.0 - self.cosine(student_emb, teacher_emb).mean()
        total_loss = self.alpha * loss_cls + (1.0 - self.alpha) * loss_distill
        return total_loss, loss_cls, loss_distill