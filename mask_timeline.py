"""Immutable, segment-local effect intervals shared by all pixel output paths."""
from dataclasses import dataclass, asdict
import json
from fastapi import HTTPException

STYLES = ('mosaic', 'blur', 'black', 'boxblur', 'horizontal', 'vertical')


@dataclass(frozen=True)
class MaskRegion:
    id: str
    start: int
    end: int
    style: str
    strength: int
    targets: tuple
    faceMode: str
    faceShape: str
    personIds: tuple
    maskPending: bool


def normalize_regions(raw, analysis, *, targets=('face',), strength=68, style='mosaic',
                      face_mode='all', person_ids=(), mask_pending=True, face_shape='circumscribed'):
    """None means legacy defaults; an explicit empty list means no effects."""
    count = len(analysis.boxes)
    if raw is None:
        return (MaskRegion('legacy', 0, count, style, strength, tuple(targets),
                           face_mode, face_shape, tuple(sorted(person_ids)), mask_pending),)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            raise HTTPException(422, 'mask_regions 必须是有效 JSON 数组')
    if not isinstance(raw, list):
        raise HTTPException(422, 'mask_regions 必须是数组')
    result, ids = [], set()
    fields = set(MaskRegion.__dataclass_fields__)
    known_people = {person['id'] for person in analysis.people}
    custom = bool(analysis.custom_masks)
    for item in raw:
        if not isinstance(item, dict) or not fields.issubset(item):
            raise HTTPException(422, 'mask_regions 条目缺少完整设置')
        key, start, end = item['id'], item['start'], item['end']
        if not isinstance(key, str) or not key.strip() or len(key) > 128 or key in ids:
            raise HTTPException(422, 'mask_regions id 必须是唯一非空字符串')
        ids.add(key)
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= count:
            raise HTTPException(422, 'mask_regions 区间必须是片段内整数半开区间')
        style, strength = item['style'], item['strength']
        if style not in STYLES or type(strength) is not int or not 20 <= strength <= 100:
            raise HTTPException(422, 'mask_regions 样式或强度无效')
        chosen = item['targets']
        if (not isinstance(chosen, list) or any(not isinstance(t, str) for t in chosen) or
                len(set(chosen)) != len(chosen) or
                any(t not in (('custom',) if custom else ('face', 'plate')) for t in chosen)):
            raise HTTPException(422, 'mask_regions 目标必须与分析类型一致')
        if item['faceMode'] not in ('all', 'selected') or item['faceShape'] not in ('inscribed', 'circumscribed'):
            raise HTTPException(422, 'mask_regions 人脸设置无效')
        people = item['personIds']
        if (not isinstance(people, list) or any(type(p) is not int or p <= 0 for p in people) or
                len(set(people)) != len(people) or not set(people).issubset(known_people) or
                type(item['maskPending']) is not bool):
            raise HTTPException(422, 'mask_regions 人物选择无效')
        result.append(MaskRegion(key, start, end, style, strength, tuple(sorted(chosen)),
                                 item['faceMode'], item['faceShape'], tuple(sorted(people)), item['maskPending']))
    result.sort(key=lambda region: (region.start, region.end))
    if any(left.end > right.start for left, right in zip(result, result[1:])):
        raise HTTPException(422, 'mask_regions 区间不可重叠')
    return tuple(result)


def regions_json(regions):
    return json.dumps([asdict(region) for region in regions], ensure_ascii=False,
                      sort_keys=True, separators=(',', ':'), allow_nan=False)


def apply_frame_config(api, frame, analysis, index, regions):
    """Apply the single active interval, returning the selected detector-box count."""
    boxes = analysis.boxes[index]
    for region in regions:
        if region.start <= index < region.end:
            selected = api.select_regions(boxes, analysis.face_ids[index], region.targets,
                                          region.faceMode, frozenset(region.personIds), region.maskPending)
            api.apply_masks(frame, selected, region.strength, region.style,
                            context=boxes, face_shape=region.faceShape)
            if 'custom' in region.targets:
                from sam_service import apply_custom
                apply_custom(frame, analysis.custom_masks[index], region.strength, region.style)
            return len(selected)
    return 0


def require_region_masks(analysis, regions):
    if any('custom' in region.targets for region in regions):
        from sam_service import require_custom
        require_custom(analysis)
