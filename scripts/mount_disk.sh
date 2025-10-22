#!/bin/bash

# 挂载磁盘脚本
# 修复自动挂载导致无法重启的问题

set -e  # 遇到错误立即退出

echo "开始磁盘挂载流程..."

# 1. 检查磁盘是否存在
echo "检查磁盘 /dev/sdb 是否存在..."
if ! fdisk -l | grep -q "Disk /dev/sdb"; then
    echo "错误: 磁盘 /dev/sdb 不存在"
    exit 1
fi
echo "✓ 磁盘 /dev/sdb 存在"

# 2. 检查是否已经存在相关的LVM组件
if vgs nvme_group >/dev/null 2>&1; then
    echo "警告: 卷组 nvme_group 已存在，跳过创建步骤"
else
    # 创建物理卷
    echo "创建物理卷..."
    pvcreate /dev/sdb
    echo "✓ 物理卷创建完成"

    # 创建卷组
    echo "创建卷组 nvme_group..."
    vgcreate nvme_group /dev/sdb
    echo "✓ 卷组创建完成"

    # 创建逻辑卷
    echo "创建逻辑卷 lv_data..."
    lvcreate -n lv_data -l 100%VG nvme_group
    echo "✓ 逻辑卷创建完成"

    # 格式化逻辑卷
    echo "格式化逻辑卷为 ext4..."
    mkfs.ext4 /dev/nvme_group/lv_data
    echo "✓ 格式化完成"
fi

# 3. 创建挂载点
echo "创建挂载点 /data..."
mkdir -p /data
echo "✓ 挂载点创建完成"

# 4. 检查逻辑卷是否存在
echo "检查逻辑卷是否存在..."
LV_PATH="/dev/mapper/nvme_group-lv_data"
LV_ALT_PATH="/dev/nvme_group/lv_data"

# 检查两种可能的路径
if [ -e "$LV_PATH" ]; then
    echo "✓ 找到逻辑卷: $LV_PATH"
elif [ -e "$LV_ALT_PATH" ]; then
    echo "✓ 找到逻辑卷: $LV_ALT_PATH"
    LV_PATH="$LV_ALT_PATH"
else
    echo "错误: 逻辑卷不存在"
    echo "请检查逻辑卷是否正确创建:"
    lvs 2>/dev/null || echo "没有找到任何逻辑卷"
    exit 1
fi

# 5. 挂载逻辑卷
echo "挂载逻辑卷到 /data..."
mount "$LV_PATH" /data -o defaults,nofail
echo "✓ 挂载完成"

# 6. 获取逻辑卷的UUID（更可靠的方式）
echo "获取逻辑卷UUID..."
LV_UUID=$(blkid -s UUID -o value "$LV_PATH")
if [ -z "$LV_UUID" ]; then
    echo "警告: 无法获取UUID，使用设备路径"
    FSTAB_DEVICE="$LV_PATH"
else
    echo "✓ 获取到UUID: $LV_UUID"
    FSTAB_DEVICE="UUID=$LV_UUID"
fi

# 7. 检查fstab中是否已存在相关条目
echo "检查 /etc/fstab 配置..."
if grep -q "/data" /etc/fstab; then
    echo "警告: /etc/fstab 中已存在 /data 挂载点配置"
    echo "现有配置:"
    grep "/data" /etc/fstab
    
    # 备份fstab
    cp /etc/fstab /etc/fstab.backup.$(date +%Y%m%d_%H%M%S)
    echo "✓ 已备份 /etc/fstab"
    
    # 移除旧的条目
    sed -i '/\/data/d' /etc/fstab
    echo "✓ 已移除旧的fstab条目"
fi

# 8. 添加到fstab（使用nofail选项防止启动失败）
echo "添加新的fstab条目..."
echo "" >> /etc/fstab
echo "$FSTAB_DEVICE /data ext4 defaults,nofail 0 2" >> /etc/fstab
echo "✓ fstab配置完成"

# 9. 验证fstab配置
echo "验证fstab配置..."
if mount -a; then
    echo "✓ fstab配置验证成功"
else
    echo "错误: fstab配置验证失败，恢复备份"
    if [ -f /etc/fstab.backup.* ]; then
        cp /etc/fstab.backup.* /etc/fstab
    fi
    exit 1
fi

# 10. 显示最终状态
echo ""
echo "========== 挂载完成 =========="
echo "挂载点: /data"
echo "设备: $LV_PATH"
if [ -n "$LV_UUID" ]; then
    echo "UUID: $LV_UUID"
fi
echo "文件系统: ext4"
echo "挂载选项: defaults,nofail"
echo ""
echo "当前挂载状态:"
df -h /data
echo ""
echo "fstab配置:"
grep "/data" /etc/fstab
echo ""
echo "✅ 磁盘挂载流程完成！系统重启时会自动挂载。"