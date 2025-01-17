"""
Modified from https://github.com/rwightman/pytorch-image-models/blob/master/timm/models/vision_transformer.py
"""
import math
import logging
from functools import partial
from collections import OrderedDict
from copy import deepcopy

import oneflow as flow
import oneflow.nn as nn
import oneflow.nn.functional as F

from flowvision.layers import trunc_normal_, lecun_normal_, PatchEmbed, Mlp, DropPath
from .helpers import named_apply
from .utils import load_state_dict_from_url
from .registry import ModelCreator


model_urls = {
    "vit_tiny_patch16_224": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_tiny_patch16_224.zip",
    "vit_tiny_patch16_384": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_tiny_patch16_384.zip",
    "vit_small_patch32_224": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_small_patch32_224.zip",
    "vit_small_patch32_384": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_small_patch32_384.zip",
    "vit_small_patch16_224": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_small_patch16_224.zip",
    "vit_small_patch16_384": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_small_patch16_384.zip",
    "vit_base_patch32_224": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_base_patch32_224.zip",
    "vit_base_patch32_384": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_base_patch32_384.zip",
    "vit_base_patch16_224": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_base_patch16_224.zip",
    "vit_base_patch16_384": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_base_patch16_384.zip",
    "vit_base_patch8_224": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_base_patch8_224.zip",
    "vit_large_patch32_224": None,
    "vit_large_patch32_384": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_large_patch32_384.zip",
    "vit_large_patch16_224": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_large_patch16_224.zip",
    "vit_large_patch16_384": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_large_patch16_384.zip",
    "vit_base_patch16_224_sam": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_base_patch16_sam_224.zip",
    "vit_base_patch32_224_sam": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_base_patch32_sam_224.zip",
    "vit_huge_patch14_224": None,
    "vit_giant_patch14_224": None,
    "vit_gigantic_patch14_224": None,
    "vit_tiny_patch16_224_in21k": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_tiny_patch16_224_in21k.zip",
    "vit_small_patch32_224_in21k": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_small_patch32_224_in21k.zip",
    "vit_small_patch16_224_in21k": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_small_patch16_224_in21k.zip",
    "vit_base_patch32_224_in21k": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_base_patch32_224_in21k.zip",
    "vit_base_patch16_224_in21k": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_base_patch16_224_in21k.zip",
    "vit_base_patch8_224_in21k": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_base_patch8_224_in21k.zip",
    "vit_large_patch32_224_in21k": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_large_patch32_224_in21k.zip",
    "vit_large_patch16_224_in21k": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_large_patch16_224_in21k.zip",
    "vit_huge_patch14_224_in21k": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_huge_patch14_224_in21k.zip",
    "deit_tiny_patch16_224": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/deit_tiny_patch16_224.zip",
    "deit_small_patch16_224": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/deit_small_patch16_224.zip",
    "deit_base_patch16_224": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/deit_base_patch16_224.zip",
    "deit_base_patch16_384": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/deit_base_patch16_384.zip",
    "deit_tiny_distilled_patch16_224": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/deit_tiny_distilled_patch16_224.zip",
    "deit_small_distilled_patch16_224": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/deit_small_distilled_patch16_224.zip",
    "deit_base_distilled_patch16_224": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/deit_base_distilled_patch16_224.zip",
    "deit_base_distilled_patch16_384": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/deit_base_distilled_patch16_384.zip",
    "vit_base_patch16_224_miil_in21k": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_base_patch16_224_miil_in21k.zip",
    "vit_base_patch16_224_miil": "https://oneflow-public.oss-cn-beijing.aliyuncs.com/model_zoo/flowvision/classification/VisionTransformer/vit_base_patch16_224_miil.zip",
}

_logger = logging.getLogger(__name__)


class Attention(nn.Module):
    def __init__(self, dim, num_heads=8, qkv_bias=False, attn_drop=0.0, proj_drop=0.0):
        super().__init__()
        self.num_heads = num_heads
        head_dim = dim // num_heads
        self.scale = head_dim ** -0.5

        self.qkv = nn.Linear(dim, dim * 3, bias=qkv_bias)
        self.attn_drop = nn.Dropout(attn_drop)
        self.proj = nn.Linear(dim, dim)
        self.proj_drop = nn.Dropout(proj_drop)

    def forward(self, x):
        B, N, C = x.shape
        qkv = (
            self.qkv(x)
            .reshape(B, N, 3, self.num_heads, C // self.num_heads)
            .permute(2, 0, 3, 1, 4)
        )
        # TODO supported tensor.unbind in oneflow
        # q, k, v = qkv.unbind(0)
        q, k, v = qkv[0], qkv[1], qkv[2]

        attn = (q @ k.transpose(-2, -1)) * self.scale
        attn = attn.softmax(dim=-1)
        attn = self.attn_drop(attn)

        x = (attn @ v).transpose(1, 2).reshape(B, N, C)
        x = self.proj(x)
        x = self.proj_drop(x)
        return x


class Block(nn.Module):
    def __init__(
        self,
        dim,
        num_heads,
        mlp_ratio=4.0,
        qkv_bias=False,
        drop=0.0,
        attn_drop=0.0,
        drop_path=0.0,
        act_layer=nn.GELU,
        norm_layer=nn.LayerNorm,
    ):
        super().__init__()
        self.norm1 = norm_layer(dim)
        self.attn = Attention(
            dim,
            num_heads=num_heads,
            qkv_bias=qkv_bias,
            attn_drop=attn_drop,
            proj_drop=drop,
        )
        # NOTE: drop path for stochastic depth, we shall see if this is better than dropout here
        self.drop_path = DropPath(drop_path) if drop_path > 0.0 else nn.Identity()
        self.norm2 = norm_layer(dim)
        mlp_hidden_dim = int(dim * mlp_ratio)
        self.mlp = Mlp(
            in_features=dim,
            hidden_features=mlp_hidden_dim,
            act_layer=act_layer,
            drop=drop,
        )

    def forward(self, x):
        x = x + self.drop_path(self.attn(self.norm1(x)))
        x = x + self.drop_path(self.mlp(self.norm2(x)))
        return x


class VisionTransformer(nn.Module):
    """ Vision Transformer
    An OneFlow impl of : `An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale`
        - https://arxiv.org/abs/2010.11929
    Includes distillation token & head support for `DeiT: Data-efficient Image Transformers`
        - https://arxiv.org/abs/2012.12877
    """

    def __init__(
        self,
        img_size=224,
        patch_size=16,
        in_chans=3,
        num_classes=1000,
        embed_dim=768,
        depth=12,
        num_heads=12,
        mlp_ratio=4.0,
        qkv_bias=True,
        representation_size=None,
        distilled=False,
        drop_rate=0.0,
        attn_drop_rate=0.0,
        drop_path_rate=0.0,
        embed_layer=PatchEmbed,
        norm_layer=None,
        act_layer=None,
        weight_init="",
    ):
        """
        Args:
            img_size (int, tuple): input image size
            patch_size (int, tuple): patch size
            in_chans (int): number of input channels
            num_classes (int): number of classes for classification head
            embed_dim (int): embedding dimension
            depth (int): depth of transformer
            num_heads (int): number of attention heads
            mlp_ratio (int): ratio of mlp hidden dim to embedding dim
            qkv_bias (bool): enable bias for qkv if True
            representation_size (Optional[int]): enable and set representation layer (pre-logits) to this value if set
            distilled (bool): model includes a distillation token and head as in DeiT models
            drop_rate (float): dropout rate
            attn_drop_rate (float): attention dropout rate
            drop_path_rate (float): stochastic depth rate
            embed_layer (nn.Module): patch embedding layer
            norm_layer: (nn.Module): normalization layer
            weight_init: (str): weight init scheme
        """
        super().__init__()
        self.num_classes = num_classes
        self.num_features = (
            self.embed_dim
        ) = embed_dim  # num_features for consistency with other models
        self.num_tokens = 2 if distilled else 1
        norm_layer = norm_layer or partial(nn.LayerNorm, eps=1e-6)
        act_layer = act_layer or nn.GELU

        self.patch_embed = embed_layer(
            img_size=img_size,
            patch_size=patch_size,
            in_chans=in_chans,
            embed_dim=embed_dim,
        )
        num_patches = self.patch_embed.num_patches

        self.cls_token = nn.Parameter(flow.zeros(1, 1, embed_dim))
        self.dist_token = (
            nn.Parameter(flow.zeros(1, 1, embed_dim)) if distilled else None
        )
        self.pos_embed = nn.Parameter(
            flow.zeros(1, num_patches + self.num_tokens, embed_dim)
        )
        self.pos_drop = nn.Dropout(p=drop_rate)

        dpr = [
            x.item() for x in flow.linspace(0, drop_path_rate, depth)
        ]  # stochastic depth decay rule
        self.blocks = nn.Sequential(
            *[
                Block(
                    dim=embed_dim,
                    num_heads=num_heads,
                    mlp_ratio=mlp_ratio,
                    qkv_bias=qkv_bias,
                    drop=drop_rate,
                    attn_drop=attn_drop_rate,
                    drop_path=dpr[i],
                    norm_layer=norm_layer,
                    act_layer=act_layer,
                )
                for i in range(depth)
            ]
        )
        self.norm = norm_layer(embed_dim)

        # Representation layer
        if representation_size and not distilled:
            self.num_features = representation_size
            self.pre_logits = nn.Sequential(
                OrderedDict(
                    [
                        ("fc", nn.Linear(embed_dim, representation_size)),
                        ("act", nn.Tanh()),
                    ]
                )
            )
        else:
            self.pre_logits = nn.Identity()

        # Classifier head(s)
        self.head = (
            nn.Linear(self.num_features, num_classes)
            if num_classes > 0
            else nn.Identity()
        )
        self.head_dist = None
        if distilled:
            self.head_dist = (
                nn.Linear(self.embed_dim, self.num_classes)
                if num_classes > 0
                else nn.Identity()
            )

        self.init_weights(weight_init)

    def init_weights(self, mode=""):
        assert mode in ("jax", "jax_nlhb", "nlhb", "")
        head_bias = -math.log(self.num_classes) if "nlhb" in mode else 0.0
        trunc_normal_(self.pos_embed, std=0.02)
        if self.dist_token is not None:
            trunc_normal_(self.dist_token, std=0.02)
        if mode.startswith("jax"):
            # leave cls token as zeros to match jax impl
            named_apply(
                partial(_init_vit_weights, head_bias=head_bias, jax_impl=True), self
            )
        else:
            trunc_normal_(self.cls_token, std=0.02)
            self.apply(_init_vit_weights)

    def _init_weights(self, m):
        # this fn left here for compat with downstream users
        _init_vit_weights(m)

    def forward_features(self, x):
        # position embedding
        x = self.patch_embed(x)

        cls_token = self.cls_token.expand(
            x.shape[0], -1, -1
        )  # stole cls_tokens impl from Phil Wang, thanks
        if self.dist_token is None:
            x = flow.cat((cls_token, x), dim=1)
        else:
            x = flow.cat(
                (cls_token, self.dist_token.expand(x.shape[0], -1, -1), x), dim=1
            )
        x = self.pos_drop(x + self.pos_embed)
        # transformer encoder
        x = self.blocks(x)
        x = self.norm(x)

        if self.dist_token is None:
            return self.pre_logits(x[:, 0])
        else:
            return x[:, 0], x[:, 1]

    def forward(self, x):
        x = self.forward_features(x)
        # classification head
        if self.head_dist is not None:
            x, x_dist = self.head(x[0]), self.head_dist(x[1])  # x must be a tuple
            if self.training:
                # during inference, return the average of both classifier predictions
                return x, x_dist
            else:
                return (x + x_dist) / 2
        else:
            x = self.head(x)
        return x


def _init_vit_weights(
    module: nn.Module, name: str = "", head_bias: float = 0.0, jax_impl: bool = False
):
    """ ViT weight initialization
    * When called without n, head_bias, jax_impl args it will behave exactly the same
      as my original init for compatibility with prev hparam / downstream use cases (ie DeiT).
    * When called w/ valid n (module name) and jax_impl=True, will (hopefully) match JAX impl
    """
    if isinstance(module, nn.Linear):
        if name.startswith("head"):
            nn.init.zeros_(module.weight)
            nn.init.constant_(module.bias, head_bias)
        elif name.startswith("pre_logits"):
            lecun_normal_(module.weight)
            nn.init.zeros_(module.bias)
        else:
            if jax_impl:
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    if "mlp" in name:
                        nn.init.normal_(module.bias, std=1e-6)
                    else:
                        nn.init.zeros_(module.bias)
            else:
                trunc_normal_(module.weight, std=0.02)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
    elif jax_impl and isinstance(module, nn.Conv2d):
        lecun_normal_(module.weight)
        if module.bias is not None:
            nn.init.zeros_(module.bias)
    elif isinstance(module, (nn.LayerNorm, nn.GroupNorm, nn.BatchNorm2d)):
        nn.init.zeros_(module.bias)
        nn.init.ones_(module.weight)


def resize_pos_embed(posemb, posemb_new, num_tokens=1, gs_new=()):
    # Rescale the grid of position embeddings when loading from state_dict. Adapted from
    # https://github.com/google-research/vision_transformer/blob/00883dd691c63a6830751563748663526e811cee/vit_jax/checkpoint.py#L224
    _logger.info("Resized position embedding: %s to %s", posemb.shape, posemb_new.shape)
    ntok_new = posemb_new.shape[1]
    if num_tokens:
        posemb_tok, posemb_grid = posemb[:, :num_tokens], posemb[0, num_tokens:]
        ntok_new -= num_tokens
    else:
        posemb_tok, posemb_grid = posemb[:, :0], posemb[0]
    gs_old = int(math.sqrt(len(posemb_grid)))
    if not len(gs_new):  # backwards compatibility
        gs_new = [int(math.sqrt(ntok_new))] * 2
    assert len(gs_new) >= 2
    _logger.info("Position embedding grid-size from %s to %s", [gs_old, gs_old], gs_new)
    posemb_grid = posemb_grid.reshape(1, gs_old, gs_old, -1).permute(0, 3, 1, 2)
    posemb_grid = F.interpolate(
        posemb_grid, size=gs_new, mode="bicubic", align_corners=False
    )
    posemb_grid = posemb_grid.permute(0, 2, 3, 1).reshape(1, gs_new[0] * gs_new[1], -1)
    posemb = flow.cat([posemb_tok, posemb_grid], dim=1)
    return posemb


def _create_vision_transformer(arch, pretrained=False, progress=True, **model_kwargs):
    model = VisionTransformer(**model_kwargs)
    if pretrained:
        state_dict = load_state_dict_from_url(model_urls[arch], progress=progress)
        model.load_state_dict(state_dict)
    return model


@ModelCreator.register_model
def vit_tiny_patch16_224(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Tiny-patch16-224 model.

    .. note::
        ViT-Tiny-patch16-224 model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_tiny_patch16_224 = flowvision.models.vit_tiny_patch16_224(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224, patch_size=16, embed_dim=192, depth=12, num_heads=3, **kwargs
    )
    model = _create_vision_transformer(
        "vit_tiny_patch16_224", pretrained=pretrained, progress=progress, **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_tiny_patch16_384(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Tiny-patch16-384 model.

    .. note::
        ViT-Tiny-patch16-384 model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 384x384.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_tiny_patch16_384 = flowvision.models.vit_tiny_patch16_384(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=384, patch_size=16, embed_dim=192, depth=12, num_heads=3, **kwargs
    )
    model = _create_vision_transformer(
        "vit_tiny_patch16_384", pretrained=pretrained, progress=progress, **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_small_patch32_224(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Small-patch32-224 model.

    .. note::
        ViT-Small-patch32-224 model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_small_patch32_224 = flowvision.models.vit_small_patch32_224(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224, patch_size=32, embed_dim=384, depth=12, num_heads=6, **kwargs
    )
    model = _create_vision_transformer(
        "vit_small_patch32_224",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_small_patch32_384(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Small-patch32-384 model.

    .. note::
        ViT-Small-patch32-384 model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 384x384.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_small_patch32_384 = flowvision.models.vit_small_patch32_384(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=384, patch_size=32, embed_dim=384, depth=12, num_heads=6, **kwargs
    )
    model = _create_vision_transformer(
        "vit_small_patch32_384",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_small_patch16_224(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Small-patch16-224 model.

    .. note::
        ViT-Small-patch16-224 model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_small_patch16_224 = flowvision.models.vit_small_patch16_224(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224, patch_size=16, embed_dim=384, depth=12, num_heads=6, **kwargs
    )
    model = _create_vision_transformer(
        "vit_small_patch16_224",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_small_patch16_384(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Small-patch16-384 model.

    .. note::
        ViT-Small-patch16-384 model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 384x384.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_small_patch16_384 = flowvision.models.vit_small_patch16_384(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=384, patch_size=16, embed_dim=384, depth=12, num_heads=6, **kwargs
    )
    model = _create_vision_transformer(
        "vit_small_patch16_384",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_base_patch32_224(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Base-patch32-224 model.

    .. note::
        ViT-Base-patch32-224 model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_base_patch32_224 = flowvision.models.vit_base_patch32_224(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224, patch_size=32, embed_dim=768, depth=12, num_heads=12, **kwargs
    )
    model = _create_vision_transformer(
        "vit_base_patch32_224", pretrained=pretrained, progress=progress, **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_base_patch32_384(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Base-patch32-384 model.

    .. note::
        ViT-Base-patch32-384 model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 384x384.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_base_patch32_384 = flowvision.models.vit_base_patch32_384(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=384, patch_size=32, embed_dim=768, depth=12, num_heads=12, **kwargs
    )
    model = _create_vision_transformer(
        "vit_base_patch32_384", pretrained=pretrained, progress=progress, **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_base_patch16_224(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Base-patch16-224 model.

    .. note::
        ViT-Base-patch16-224 model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_base_patch16_224 = flowvision.models.vit_base_patch16_224(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224, patch_size=16, embed_dim=768, depth=12, num_heads=12, **kwargs
    )
    model = _create_vision_transformer(
        "vit_base_patch16_224", pretrained=pretrained, progress=progress, **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_base_patch16_384(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Base-patch16-384 model.

    .. note::
        ViT-Base-patch16-384 model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 384x384.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_base_patch16_384 = flowvision.models.vit_base_patch16_384(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=384, patch_size=16, embed_dim=768, depth=12, num_heads=12, **kwargs
    )
    model = _create_vision_transformer(
        "vit_base_patch16_384", pretrained=pretrained, progress=progress, **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_base_patch8_224(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Base-patch8-224 model.

    .. note::
        ViT-Base-patch8-224 model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_base_patch8_224 = flowvision.models.vit_base_patch8_224(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224, patch_size=8, embed_dim=768, depth=12, num_heads=12, **kwargs
    )
    model = _create_vision_transformer(
        "vit_base_patch8_224", pretrained=pretrained, progress=progress, **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_large_patch32_224(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Large-patch32-224 model.

    .. note::
        ViT-Large-patch32-224 model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_large_patch32_224 = flowvision.models.vit_large_patch32_224(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224, patch_size=32, embed_dim=1024, depth=24, num_heads=16, **kwargs
    )
    model = _create_vision_transformer(
        "vit_large_patch32_224",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_large_patch32_384(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Large-patch32-384 model.

    .. note::
        ViT-Large-patch32-384 model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 384x384.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_large_patch32_384 = flowvision.models.vit_large_patch32_384(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=384, patch_size=32, embed_dim=1024, depth=24, num_heads=16, **kwargs
    )
    model = _create_vision_transformer(
        "vit_large_patch32_384",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_large_patch16_224(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Large-patch16-224 model.

    .. note::
        ViT-Large-patch16-224 model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_large_patch16_224 = flowvision.models.vit_large_patch16_224(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224, patch_size=16, embed_dim=1024, depth=24, num_heads=16, **kwargs
    )
    model = _create_vision_transformer(
        "vit_large_patch16_224",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_large_patch16_384(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Large-patch16-384 model.

    .. note::
        ViT-Large-patch16-384 model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 384x384.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_large_patch16_384 = flowvision.models.vit_large_patch16_384(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=384, patch_size=16, embed_dim=1024, depth=24, num_heads=16, **kwargs
    )
    model = _create_vision_transformer(
        "vit_large_patch16_384",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_base_patch16_224_sam(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Base-patch16-224-sam model.

    .. note::
        ViT-Base-patch16-224-sam model from `"When Vision Transformers Outperform ResNets without Pre-training or Strong Data Augmentations" <https://arxiv.org/pdf/2106.01548.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_base_patch16_224_sam = flowvision.models.vit_base_patch16_224_sam(pretrained=False, progress=True)

    """
    # NOTE original SAM weights release worked with representation_size=768
    model_kwargs = dict(
        img_size=224,
        patch_size=16,
        embed_dim=768,
        depth=12,
        num_heads=12,
        representation_size=0,
        **kwargs
    )
    model = _create_vision_transformer(
        "vit_base_patch16_224_sam",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_base_patch32_224_sam(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Base-patch32-224-sam model.

    .. note::
        ViT-Base-patch32-224-sam model from `"When Vision Transformers Outperform ResNets without Pre-training or Strong Data Augmentations" <https://arxiv.org/pdf/2106.01548.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_base_patch32_224_sam = flowvision.models.vit_base_patch32_224_sam(pretrained=False, progress=True)

    """
    # NOTE original SAM weights release worked with representation_size=768
    model_kwargs = dict(
        img_size=224,
        patch_size=32,
        embed_dim=768,
        depth=12,
        num_heads=12,
        representation_size=0,
        **kwargs
    )
    model = _create_vision_transformer(
        "vit_base_patch32_224_sam",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_huge_patch14_224(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Huge-patch14-224 model.

    .. note::
        ViT-Huge-patch14-224 model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_huge_patch14_224 = flowvision.models.vit_huge_patch14_224(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=384, patch_size=14, embed_dim=1280, depth=32, num_heads=16, **kwargs
    )
    model = _create_vision_transformer(
        "vit_huge_patch14_224", pretrained=pretrained, progress=progress, **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_giant_patch14_224(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Giant-patch14-224 model.

    .. note::
        ViT-Giant-patch14-224 model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_giant_patch14_224 = flowvision.models.vit_giant_patch14_224(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224,
        patch_size=14,
        embed_dim=1408,
        mlp_ratio=48 / 11,
        depth=40,
        num_heads=16,
        **kwargs
    )
    model = _create_vision_transformer(
        "vit_giant_patch14_224",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_gigantic_patch14_224(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Gigantic-patch14-224 model.

    .. note::
        ViT-Giant-patch14-224 model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_gigantic_patch14_224 = flowvision.models.vit_gigantic_patch14_224(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=384,
        patch_size=14,
        embed_dim=1664,
        mlp_ratio=64 / 13,
        depth=48,
        num_heads=16,
        **kwargs
    )
    model = _create_vision_transformer(
        "vit_gigantic_patch14_224",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_tiny_patch16_224_in21k(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Tiny-patch16-224 ImageNet21k pretrained model.

    .. note::
        ViT-Tiny-patch16-224 ImageNet21k pretrained model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_tiny_patch16_224_in21k = flowvision.models.vit_tiny_patch16_224_in21k(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224,
        patch_size=16,
        embed_dim=192,
        depth=12,
        num_heads=3,
        num_classes=21843,
        **kwargs
    )
    model = _create_vision_transformer(
        "vit_tiny_patch16_224_in21k",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_small_patch32_224_in21k(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Small-patch32-224 ImageNet21k pretrained model.

    .. note::
        ViT-Small-patch32-224 ImageNet21k pretrained model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_small_patch32_224_in21k = flowvision.models.vit_small_patch32_224_in21k(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224,
        patch_size=32,
        embed_dim=384,
        depth=12,
        num_heads=6,
        num_classes=21843,
        **kwargs
    )
    model = _create_vision_transformer(
        "vit_small_patch32_224_in21k",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_small_patch16_224_in21k(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Small-patch16-224 ImageNet21k pretrained model.

    .. note::
        ViT-Small-patch16-224 ImageNet21k pretrained model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_small_patch16_224_in21k = flowvision.models.vit_small_patch16_224_in21k(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224,
        patch_size=16,
        embed_dim=384,
        depth=12,
        num_heads=6,
        num_classes=21843,
        **kwargs
    )
    model = _create_vision_transformer(
        "vit_small_patch32_224_in21k",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_base_patch32_224_in21k(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Base-patch32-224 ImageNet21k pretrained model.

    .. note::
        ViT-Base-patch32-224 ImageNet21k pretrained model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_base_patch32_224_in21k = flowvision.models.vit_base_patch32_224_in21k(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224,
        patch_size=32,
        embed_dim=768,
        depth=12,
        num_heads=12,
        num_classes=21843,
        **kwargs
    )
    model = _create_vision_transformer(
        "vit_base_patch32_224_in21k",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_base_patch16_224_in21k(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Base-patch16-224 ImageNet21k pretrained model.

    .. note::
        ViT-Base-patch16-224 ImageNet21k pretrained model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_base_patch16_224_in21k = flowvision.models.vit_base_patch16_224_in21k(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224,
        patch_size=16,
        embed_dim=768,
        depth=12,
        num_heads=12,
        num_classes=21843,
        **kwargs
    )
    model = _create_vision_transformer(
        "vit_base_patch16_224_in21k",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_base_patch8_224_in21k(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Base-patch8-224 ImageNet21k pretrained model.

    .. note::
        ViT-Base-patch8-224 ImageNet21k pretrained model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_base_patch8_224_in21k = flowvision.models.vit_base_patch8_224_in21k(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224,
        patch_size=8,
        embed_dim=768,
        depth=12,
        num_heads=12,
        num_classes=21843,
        **kwargs
    )
    model = _create_vision_transformer(
        "vit_base_patch8_224_in21k",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_large_patch32_224_in21k(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Large-patch32-224 ImageNet21k pretrained model.

    .. note::
        ViT-Large-patch32-224 ImageNet21k pretrained model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_large_patch32_224_in21k = flowvision.models.vit_large_patch32_224_in21k(pretrained=False, progress=True)

    """
    # NOTE: this model has a representation layer but the 21k classifier head is zero'd out in original weights
    model_kwargs = dict(
        img_size=224,
        patch_size=32,
        embed_dim=1024,
        depth=24,
        num_heads=16,
        num_classes=21843,
        representation_size=1024,
        **kwargs
    )
    model = _create_vision_transformer(
        "vit_large_patch32_224_in21k",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_large_patch16_224_in21k(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Large-patch16-224 ImageNet21k pretrained model.

    .. note::
        ViT-Large-patch16-224 ImageNet21k pretrained model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_large_patch16_224_in21k = flowvision.models.vit_large_patch16_224_in21k(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224,
        patch_size=16,
        embed_dim=1024,
        depth=24,
        num_heads=16,
        num_classes=21843,
        **kwargs
    )
    model = _create_vision_transformer(
        "vit_large_patch16_224_in21k",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_huge_patch14_224_in21k(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Huge-patch14-224 ImageNet21k pretrained model.

    .. note::
        ViT-Huge-patch14-224 ImageNet21k pretrained model from `"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" <https://arxiv.org/pdf/2010.11929.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_huge_patch14_224_in21k = flowvision.models.vit_huge_patch14_224_in21k(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224,
        patch_size=14,
        embed_dim=1280,
        depth=32,
        num_heads=16,
        representation_size=1280,
        num_classes=21843,
        **kwargs
    )
    model = _create_vision_transformer(
        "vit_huge_patch14_224_in21k",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def deit_tiny_patch16_224(pretrained=False, progress=True, **kwargs):
    """
    Constructs the DeiT-Tiny-patch16-224 model.

    .. note::
        DeiT-Tiny-patch16-224 model from `"Training data-efficient image transformers & distillation through attention" <https://arxiv.org/pdf/2012.12877.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> deit_tiny_patch16_224 = flowvision.models.deit_tiny_patch16_224(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224, patch_size=16, embed_dim=192, depth=12, num_heads=3, **kwargs
    )
    model = _create_vision_transformer(
        "deit_tiny_patch16_224",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def deit_small_patch16_224(pretrained=False, progress=True, **kwargs):
    """
    Constructs the DeiT-Small-patch16-224 model.

    .. note::
        DeiT-Small-patch16-224 model from `"Training data-efficient image transformers & distillation through attention" <https://arxiv.org/pdf/2012.12877.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> deit_small_patch16_224 = flowvision.models.deit_small_patch16_224(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224, patch_size=16, embed_dim=384, depth=12, num_heads=6, **kwargs
    )
    model = _create_vision_transformer(
        "deit_small_patch16_224",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def deit_base_patch16_224(pretrained=False, progress=True, **kwargs):
    """
    Constructs the DeiT-Base-patch16-224 model.

    .. note::
        DeiT-Base-patch16-224 model from `"Training data-efficient image transformers & distillation through attention" <https://arxiv.org/pdf/2012.12877.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> deit_base_patch16_224 = flowvision.models.deit_base_patch16_224(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224, patch_size=16, embed_dim=768, depth=12, num_heads=12, **kwargs
    )
    model = _create_vision_transformer(
        "deit_base_patch16_224",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def deit_base_patch16_384(pretrained=False, progress=True, **kwargs):
    """
    Constructs the DeiT-Base-patch16-384 model.

    .. note::
        DeiT-Base-patch16-384 model from `"Training data-efficient image transformers & distillation through attention" <https://arxiv.org/pdf/2012.12877.pdf>`_.
        The required input size of the model is 384x384.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> deit_base_patch16_384 = flowvision.models.deit_base_patch16_384(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=384, patch_size=16, embed_dim=768, depth=12, num_heads=12, **kwargs
    )
    model = _create_vision_transformer(
        "deit_base_patch16_384",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def deit_tiny_distilled_patch16_224(pretrained=False, progress=True, **kwargs):
    """
    Constructs the DeiT-Tiny-patch16-224 distilled model.

    .. note::
        DeiT-Tiny-patch16-224 distilled model from `"Training data-efficient image transformers & distillation through attention" <https://arxiv.org/pdf/2012.12877.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> deit_tiny_distilled_patch16_224 = flowvision.models.deit_tiny_distilled_patch16_224(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224,
        patch_size=16,
        embed_dim=192,
        depth=12,
        num_heads=3,
        distilled=True,
        **kwargs
    )
    model = _create_vision_transformer(
        "deit_tiny_distilled_patch16_224",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def deit_small_distilled_patch16_224(pretrained=False, progress=True, **kwargs):
    """
    Constructs the DeiT-Small-patch16-224 distilled model.

    .. note::
        DeiT-Small-patch16-224 distilled model from `"Training data-efficient image transformers & distillation through attention" <https://arxiv.org/pdf/2012.12877.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> deit_small_distilled_patch16_224 = flowvision.models.deit_small_distilled_patch16_224(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224,
        patch_size=16,
        embed_dim=384,
        depth=12,
        num_heads=6,
        distilled=True,
        **kwargs
    )
    model = _create_vision_transformer(
        "deit_small_distilled_patch16_224",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def deit_base_distilled_patch16_224(pretrained=False, progress=True, **kwargs):
    """
    Constructs the DeiT-Base-patch16-224 distilled model.

    .. note::
        DeiT-Base-patch16-224 distilled model from `"Training data-efficient image transformers & distillation through attention" <https://arxiv.org/pdf/2012.12877.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> deit_base_distilled_patch16_224 = flowvision.models.deit_base_distilled_patch16_224(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224,
        patch_size=16,
        embed_dim=768,
        depth=12,
        num_heads=12,
        distilled=True,
        **kwargs
    )
    model = _create_vision_transformer(
        "deit_base_distilled_patch16_224",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def deit_base_distilled_patch16_384(pretrained=False, progress=True, **kwargs):
    """
    Constructs the DeiT-Base-patch16-384 distilled model.

    .. note::
        DeiT-Base-patch16-384 distilled model from `"Training data-efficient image transformers & distillation through attention" <https://arxiv.org/pdf/2012.12877.pdf>`_.
        The required input size of the model is 384x384.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> deit_base_distilled_patch16_384 = flowvision.models.deit_base_distilled_patch16_384(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=384,
        patch_size=16,
        embed_dim=768,
        depth=12,
        num_heads=12,
        distilled=True,
        **kwargs
    )
    model = _create_vision_transformer(
        "deit_base_distilled_patch16_384",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_base_patch16_224_miil_in21k(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Base-patch16-224-miil ImageNet21k pretrained model.

    .. note::
        ViT-Base-patch16-224-miil ImageNet21k pretrained model from `"Training data-efficient image transformers & distillation through attention" <https://arxiv.org/pdf/2012.12877.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_base_patch16_224_miil_in21k = flowvision.models.vit_base_patch16_224_miil_in21k(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224,
        patch_size=16,
        embed_dim=768,
        depth=12,
        num_heads=12,
        qkv_bias=False,
        num_classes=11221,
        **kwargs
    )
    model = _create_vision_transformer(
        "vit_base_patch16_224_miil_in21k",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model


@ModelCreator.register_model
def vit_base_patch16_224_miil(pretrained=False, progress=True, **kwargs):
    """
    Constructs the ViT-Base-patch16-224-miil model.

    .. note::
        ViT-Base-patch16-224-miil model from `"Training data-efficient image transformers & distillation through attention" <https://arxiv.org/pdf/2012.12877.pdf>`_.
        The required input size of the model is 224x224.

    Args:
        pretrained (bool): Whether to download the pre-trained model on ImageNet. Default: ``False``
        progress (bool): If True, displays a progress bar of the download to stderr. Default: ``True``

    For example:

    .. code-block:: python

        >>> import flowvision
        >>> vit_base_patch16_224_miil = flowvision.models.vit_base_patch16_224_miil(pretrained=False, progress=True)

    """
    model_kwargs = dict(
        img_size=224,
        patch_size=16,
        embed_dim=768,
        depth=12,
        num_heads=12,
        qkv_bias=False,
        **kwargs
    )
    model = _create_vision_transformer(
        "vit_base_patch16_224_miil",
        pretrained=pretrained,
        progress=progress,
        **model_kwargs
    )
    return model
