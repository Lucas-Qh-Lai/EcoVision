"""
EcoVision - 垃圾分类指南数据库（四大类详细版）
"""

import json
import os

_GUIDES = {}

CATEGORY_ALIAS = {
    "其它垃圾": "其他垃圾",
    "可回收垃圾": "可回收物",
}

CATEGORY_INFO = {
    "可回收物": {"color": "#3B82F6", "icon": "♻️", "label": "可回收垃圾"},
    "有害垃圾": {"color": "#EF4444", "icon": "☣️", "label": "有害垃圾"},
    "厨余垃圾": {"color": "#10B981", "icon": "🍃", "label": "厨余垃圾"},
    "其他垃圾": {"color": "#6B7280", "icon": "🗑️", "label": "其他垃圾"},
}

_CATEGORY_LABEL_TO_KEY = {
    info["label"]: key for key, info in CATEGORY_INFO.items()
}

CATEGORY_GUIDES = {
    "可回收物": {
        "tips": [
            "清洁干净后投入蓝色可回收物桶",
            "纸类叠放整齐，纸箱拆解压平后投放，胶带需撕除",
            "塑料瓶、洗发水瓶等压扁后再投放，减少体积",
            "玻璃制品轻拿轻放，投入可回收物桶，避免破碎",
            "金属制品（易拉罐、锅具等）清洗后投放",
            "旧衣物、纺织品清洗干净后投入衣物回收箱",
            "电子废弃物（手机、充电器等）应送至专业回收点",
            "快递纸箱、包装盒拆开压平，去除胶带和填充物",
        ],
    },
    "有害垃圾": {
        "tips": [
            "电池（含纽扣电池）单独收集，不可混入其他垃圾",
            "过期药品请保留包装或说明书，投入红色有害垃圾桶",
            "废灯管、温度计等易碎品轻拿轻放，包裹后投放，防止破损泄漏",
            "杀虫剂、空气清新剂等确认罐内已用空后再投放",
            "指甲油、洗甲水、染发剂等化妆品废弃物投入有害垃圾桶",
            "充电电池、蓄电池等应送至专门回收点",
            "废胶片、废相纸、废油漆桶等均属于有害垃圾",
        ],
    },
    "厨余垃圾": {
        "tips": [
            "投放前请尽量沥干水分，减少垃圾处理负担",
            "将食物残余与包装物（塑料袋、餐盒）分离，只投放厨余部分",
            "大骨棒、贝壳、榴莲壳等硬质物属于其他垃圾，请勿混入厨余",
            "避免混入牙签、纸巾、塑料绳、一次性餐具等杂物",
            "剩饭剩菜倒进厨余桶，装剩菜的塑料袋投入其他垃圾桶",
            "茶渣、咖啡渣、果皮果核、残枝落叶等属于厨余垃圾",
            "废弃食用油应装入容器密封后投入厨余垃圾桶",
            "玉米芯、坚果壳等质地坚硬的厨余垃圾也属于此类别",
        ],
    },
    "其他垃圾": {
        "tips": [
            "尽量沥干水分后投入灰色其他垃圾桶",
            "破碎陶瓷、玻璃碎片请用纸或布包裹后再投放，避免划伤清洁人员",
            "使用过的纸巾、湿巾、纸尿裤、卫生用品等属于其他垃圾",
            "一次性餐具、奶茶杯、方便面桶、餐盒等应沥干内容物后投放",
            "尘土、灰渣、烟蒂、猫砂等应投入其他垃圾桶",
            "创可贴、口罩、医用胶带等卫生用品属于其他垃圾",
            "大件垃圾（旧家具、床垫等）应预约回收或投放至大件垃圾站",
            "陶瓷制品、花盆、瓦片等建筑垃圾不属于生活垃圾，需另行处理",
        ],
    },
}


def get_category(label: str) -> str:
    if "-" in label:
        cat = label.split("-")[0]
        return CATEGORY_ALIAS.get(cat, cat)
    # Fallback: look up from guides.json if available
    if _GUIDES and label in _GUIDES:
        guide_cat = _GUIDES[label].get("category", "")
        return _CATEGORY_LABEL_TO_KEY.get(guide_cat, "其他垃圾")
    return "其他垃圾"


def get_display_name(label: str) -> str:
    if "-" in label:
        return label.split("-", 1)[1]
    return label


def get_category_info(category: str) -> dict:
    return CATEGORY_INFO.get(category, CATEGORY_INFO["其他垃圾"])


def load_guides(path: str = "guides.json"):
    global _GUIDES
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            _GUIDES = json.load(f)
        print(f"[guides_db] 已加载 {len(_GUIDES)} 条指南数据结构")
    else:
        print(f"[guides_db] 未找到 {path}")


def get_guide(label: str) -> dict:
    """根据模型标签获取四大类处理指南"""
    if _GUIDES and label in _GUIDES:
        return _GUIDES[label]
    category = get_category(label)
    category = CATEGORY_ALIAS.get(category, category)
    info = get_category_info(category)
    guide = CATEGORY_GUIDES.get(category, CATEGORY_GUIDES["其他垃圾"])

    return {
        "display_name": get_display_name(label),
        "category": info["label"],
        "color": info["color"],
        "icon": info["icon"],
        "tips": guide["tips"],
    }


def eval_after_build(labels: list, guides: dict):
    """兼容旧接口"""
    global _GUIDES
    _GUIDES = guides
