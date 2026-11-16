"""Immutable ordered layer snapshots shared by preview, playback and export."""
from dataclasses import dataclass
import json
from fastapi import HTTPException
from .mask_timeline import normalize_regions, require_region_masks, regions_json, apply_frame_config


@dataclass(frozen=True)
class MaskLayer:
    analysis_id: str
    analysis: object
    regions: tuple


def normalize_layers(api, anchor, raw):
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            raise HTTPException(422, 'layers 必须是有效 JSON 数组')
    if not isinstance(raw, list):
        raise HTTPException(422, 'layers 必须是数组')
    result = []
    identity = lambda a: (a.input_path.resolve(), a.start_frame, len(a.boxes), a.fps, a.width, a.height)
    for item in raw:
        if (not isinstance(item, dict) or set(item) != {'analysis_id', 'mask_regions'} or
                not isinstance(item['analysis_id'], str) or not item['analysis_id'] or
                not isinstance(item['mask_regions'], list)):
            raise HTTPException(422, '每层必须包含 analysis_id 和 mask_regions 数组')
        analysis = api.require_analysis(item['analysis_id'])
        if identity(analysis) != identity(anchor):
            raise HTTPException(422, '所有层必须属于相同媒体、帧范围、帧率和尺寸')
        regions = normalize_regions(item['mask_regions'], analysis)
        require_region_masks(analysis, regions)
        from .sam_service import DiskMasks
        if not isinstance(analysis.custom_masks, DiskMasks) and any(mask.flags.writeable for mask in analysis.custom_masks):
            raise HTTPException(409, '自定义遮罩缓存必须冻结')
        if (len(analysis.face_ids) != len(analysis.boxes) or
                any(len(boxes) != len(ids) for boxes, ids in zip(analysis.boxes, analysis.face_ids))):
            raise HTTPException(409, '分析缓存不完整')
        result.append(MaskLayer(item['analysis_id'], analysis, regions))
    return tuple(result)


def layers_json(layers):
    return json.dumps([{'analysis_id': layer.analysis_id, 'mask_regions': json.loads(regions_json(layer.regions))}
                       for layer in layers], ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def apply_layers(api, frame, index, layers):
    return sum(apply_frame_config(api, frame, layer.analysis, index, layer.regions) for layer in layers)
