import requests
import json

# 华为设备序列号列表
sn_list = [
    "",""
]

# API端点
api_endpoint = "http://localhost:9876/sn_query/huawei"

# 存储查询结果
results = []

print("开始批量查询华为设备维保信息...")
print("=" * 80)

for sn in sn_list:
    print(f"查询序列号: {sn}")
    
    try:
        # 发送GET请求
        response = requests.get(f"{api_endpoint}?sn={sn}", timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success") == 1:
                if data.get("data"):
                    # 每个序列号可能有多个维保记录
                    for item in data["data"]:
                        item["序列号"] = sn  # 确保序列号在结果中
                        results.append(item)
                    print(f"✓ 查询成功，找到 {len(data['data'])} 条记录")
                else:
                    print(f"✗ 查询成功，但未找到维保记录")
                    # 添加空记录，确保所有序列号都在结果中
                    results.append({"序列号": sn, "设备型号": "", "服务套餐": "", "开始日期": "", "结束日期": "", "状态": "", "国家/地区": "", "保修区域": "", "描述": "未找到维保记录"})
            else:
                print(f"✗ 查询失败: {data.get('message', '未知错误')}")
                # 添加错误记录
                results.append({"序列号": sn, "设备型号": "", "服务套餐": "", "开始日期": "", "结束日期": "", "状态": "", "国家/地区": "", "保修区域": "", "描述": f"查询失败: {data.get('message', '未知错误')}"})
        else:
            print(f"✗ 请求失败，状态码: {response.status_code}")
            # 添加错误记录
            results.append({"序列号": sn, "设备型号": "", "服务套餐": "", "开始日期": "", "结束日期": "", "状态": "", "国家/地区": "", "保修区域": "", "描述": f"请求失败，状态码: {response.status_code}"})
    except Exception as e:
        print(f"✗ 发生异常: {str(e)}")
        # 添加异常记录
        results.append({"序列号": sn, "设备型号": "", "服务套餐": "", "开始日期": "", "结束日期": "", "状态": "", "国家/地区": "", "保修区域": "", "描述": f"发生异常: {str(e)}"})
    
    print("-" * 80)

print("批量查询完成！")
print("=" * 80)

# 生成Markdown表格
print("\n## 华为设备维保信息查询结果\n")
print("| 序列号 | 设备型号 | 服务套餐 | 开始日期 | 结束日期 | 状态 | 国家/地区 | 保修区域 | 描述 |")
print("|--------|----------|----------|----------|----------|------|----------|----------|------|")

for item in results:
    row = f"| {item.get('序列号', '')} | {item.get('设备型号', '')} | {item.get('服务套餐', '')} | {item.get('开始日期', '')} | {item.get('结束日期', '')} | {item.get('状态', '')} | {item.get('国家/地区', '')} | {item.get('保修区域', '')} | {item.get('描述', '')} |"
    print(row)

# 保存结果到JSON文件
with open('query_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\n查询结果已保存到 query_results.json 文件")
