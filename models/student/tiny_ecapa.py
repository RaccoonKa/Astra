import torch
import torch.nn as nn
import torch.nn.functional as F


class SEBlock(nn.Module):
    def __init__(self, channels, bottleneck=32):
        super().__init__()
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.fc = nn.Sequential(
            nn.Linear(channels, bottleneck, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(bottleneck, channels, bias=False),
            nn.Sigmoid()
        )

    def forward(self, x):
        b, c, _ = x.shape
        w = self.pool(x).view(b, c)
        w = self.fc(w).view(b, c, 1)
        return x * w


class Res2NetBlock(nn.Module):
    def __init__(self, channels=128, kernel_size=3, dilation=2, scale=4):
        super().__init__()
        self.scale = scale
        self.width = channels // scale
        self.convs = nn.ModuleList([
            nn.Conv1d(
                self.width, self.width, kernel_size,
                padding=(kernel_size - 1) * dilation // 2,
                dilation=dilation, bias=False
            ) for _ in range(scale - 1)
        ])
        self.bns = nn.ModuleList([nn.BatchNorm1d(self.width) for _ in range(scale - 1)])
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        chunks = torch.split(x, self.width, dim=1)
        out = []
        y = None
        for i in range(self.scale):
            if i == 0:
                out.append(chunks[0])
            elif i == 1:
                y = self.relu(self.bns[i - 1](self.convs[i - 1](chunks[i])))
                out.append(y)
            else:
                y = chunks[i] + y
                y = self.relu(self.bns[i - 1](self.convs[i - 1](y)))
                out.append(y)
        return torch.cat(out, dim=1)


class SERes2NetBlock(nn.Module):
    def __init__(self, channels=128, kernel_size=3, dilation=2, scale=4):
        super().__init__()
        self.conv1 = nn.Conv1d(channels, channels, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm1d(channels)
        self.res2net = Res2NetBlock(channels, kernel_size, dilation, scale)
        self.conv2 = nn.Conv1d(channels, channels, kernel_size=1, bias=False)
        self.bn2 = nn.BatchNorm1d(channels)
        self.se = SEBlock(channels)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        residual = x
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.res2net(out)
        out = self.bn2(self.conv2(out))
        out = self.se(out)
        out += residual
        return self.relu(out)


class AttentiveStatsPool(nn.Module):
    def __init__(self, in_dim=384, hidden_dim=128):
        super().__init__()
        self.attention = nn.Sequential(
            nn.Conv1d(in_dim, hidden_dim, kernel_size=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm1d(hidden_dim),
            nn.Conv1d(hidden_dim, in_dim, kernel_size=1),
            nn.Softmax(dim=2)
        )

    def forward(self, x):
        alpha = self.attention(x)
        mean = torch.sum(alpha * x, dim=2)
        residuals = x - mean.unsqueeze(2)
        variance = torch.sum(alpha * (residuals ** 2), dim=2)
        std = torch.sqrt(torch.clamp(variance, min=1e-8))
        return torch.cat([mean, std], dim=1)


class TinyECAPA(nn.Module):
    def __init__(self, in_features=80, channels=128, emb_dim=192):
        super().__init__()
        self.in_conv = nn.Sequential(
            nn.Conv1d(in_features, channels, kernel_size=5, padding=2, bias=False),
            nn.BatchNorm1d(channels),
            nn.ReLU(inplace=True)
        )
        self.block1 = SERes2NetBlock(channels, dilation=2)
        self.block2 = SERes2NetBlock(channels, dilation=3)
        self.block3 = SERes2NetBlock(channels, dilation=4)

        self.mfa_dim = channels * 3
        self.asp = AttentiveStatsPool(in_dim=self.mfa_dim, hidden_dim=96)
        self.fc = nn.Linear(self.mfa_dim * 2, emb_dim)
        self.bn_out = nn.BatchNorm1d(emb_dim)

    def forward(self, x):
        feat = self.in_conv(x)
        out1 = self.block1(feat)
        out2 = self.block2(out1)
        out3 = self.block3(out2)

        mfa = torch.cat([out1, out2, out3], dim=1)
        pooled = self.asp(mfa)
        emb = self.bn_out(self.fc(pooled))
        return F.normalize(emb, p=2, dim=-1)


if __name__ == "__main__":
    model = TinyECAPA(in_features=80, channels=128, emb_dim=192)
    dummy_input = torch.randn(2, 80, 200)
    out = model(dummy_input)

    total_params = sum(p.numel() for p in model.parameters())
    print(f"Выходной тензор: {out.shape}")
    print(f"Параметров: {total_params:,} ({total_params * 4 / 1024 / 1024:.2f} МБ в FP32)")