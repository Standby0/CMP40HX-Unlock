package hxcore

import (
	"strings"
	"syscall"
	"time"
)

// SS0 算力解锁寄存器偏移 (BAR0)
const SS0Offset = 0x409664

// SS1 偏移 (副标志)
const SS1Offset = 0x409668

// UnlockState: 一次"解锁是否成功"实测快照
type UnlockState struct {
	BridgeOK  bool   // \\.\40hxBridge 可打开
	WinRingOK bool   // \\.\WinRing0_1_2_0 可打开
	TSOK      bool   // \\.\ThrottleStop 可打开 (v2.5 BYOVD 通道)
	Speed     uint32 // PCIe gen (0=未知)
	SS0       uint32 // 算力标志寄存器
	SS1       uint32
	SS0OK     bool // 成功读到 SS0
	Unlocked  bool // SS0 == 0x88888888
}

// FindGPUPCI: 全扫 PCI config 定位 40HX 的 BDF (bus<<8|dev<<3|fn)。
// 只认 VEN_10DE + DEV_1F0B — 多卡/非 bus1 拓扑也不会认错设备。
// bus 0..255 全扫：AGESA 主板(如 MSI B450 H.P3)把 PEG 槽编到 bus 0x10、
// iGPU 到 0x30 — 旧的 bus<8 上限在这些板上永远找不到卡。
// fn0 先读+multifunction 判定后跳 fn1-7，避免 256 总线 × 8 fn 全量 ioctl。
func FindGPUPCI(wh syscall.Handle) (uint32, bool) {
	for bus := uint32(0); bus < 256; bus++ {
		for dev := uint32(0); dev < 32; dev++ {
			bdf0 := (bus << 8) | (dev << 3)
			id0, err := PciRd(wh, bdf0, 0x00)
			if err != nil || id0 == 0xFFFFFFFF || (id0&0xFFFF) == 0 {
				continue
			}
			maxFn := uint32(1)
			if hdr, _ := PciRd(wh, bdf0, 0x0C); hdr&0x800000 != 0 {
				maxFn = 8
			}
			for fn := uint32(0); fn < maxFn; fn++ {
				bdf := bdf0 | fn
				id := id0
				if fn != 0 {
					id, err = PciRd(wh, bdf, 0x00)
					if err != nil || id == 0xFFFFFFFF {
						continue
					}
				}
				if id&0xFFFF == 0x10DE && (id>>16)&0xFFFF == 0x1F0B {
					return bdf, true
				}
			}
		}
	}
	return 0, false
}

// ReadUnlockState: 打开两驱动并读 SS0/SS1/链路速率。
// retries: 驱动未就绪(刚进桌面驱动还在加载)时的重试次数;
// delayMs: 每次重试间隔。适合登录后立刻调用时等待驱动就绪。
func ReadUnlockState(retries int, delayMs int) *UnlockState {
	st := &UnlockState{}
	bh, err1 := OpenDevice(`\\.\40hxBridge`)
	wh, err2 := OpenDevice(`\\.\WinRing0_1_2_0`)
	for i := 0; (err1 != nil || err2 != nil) && i < retries; i++ {
		if err1 != nil {
			bh, err1 = OpenDevice(`\\.\40hxBridge`)
		}
		if err2 != nil {
			wh, err2 = OpenDevice(`\\.\WinRing0_1_2_0`)
		}
		time.Sleep(time.Duration(delayMs) * time.Millisecond)
	}
	if err1 != nil || err2 != nil {
		if err1 != nil {
			CloseHandle(bh)
		}
		if err2 != nil {
			CloseHandle(wh)
		}
		return st
	}
	defer CloseHandle(bh)
	defer CloseHandle(wh)
	st.BridgeOK, st.WinRingOK = true, true

	// PCIe gen: 先按 VEN/DEV 定位 40HX 的 BDF, 再读它的 link speed
	// (不校验设备身份会误读其它 PCIe 设备的速率 — 多卡/非 bus1 拓扑的坑)
	if bdf, ok := FindGPUPCI(wh); ok {
		st.Speed = LinkSpeed(wh, bdf)
	}
	if v, err := Bar0Rd(bh, SS0Offset); err == nil {
		st.SS0, st.SS0OK = v, true
		st.Unlocked = v == 0x88888888
	}
	if v, err := Bar0Rd(bh, SS1Offset); err == nil {
		st.SS1 = v
	}
	return st
}

// ReadUnlockStateV2: v2.5 通道 — WinRing0(config: 链路/找卡/BAR0 基址) +
// ThrottleStop(BYOVD, 读 SS0/SS1)。普通模式、无 40hx_bridge、无测试签名也能判定。
func ReadUnlockStateV2(retries int, delayMs int) *UnlockState {
	st := &UnlockState{}
	wh, err2 := OpenDevice(`\\.\WinRing0_1_2_0`)
	for i := 0; err2 != nil && i < retries; i++ {
		wh, err2 = OpenDevice(`\\.\WinRing0_1_2_0`)
		time.Sleep(time.Duration(delayMs) * time.Millisecond)
	}
	if err2 != nil {
		return st // 无 WinRing0 就无法读 config / BAR0 基址
	}
	defer CloseHandle(wh)
	st.WinRingOK = true

	bdf, ok := FindGPUPCI(wh)
	if !ok {
		return st
	}
	st.Speed = LinkSpeed(wh, bdf)
	bar0raw, err := PciRd(wh, bdf, 0x10)
	if err != nil {
		return st
	}
	bar0 := uint64(bar0raw & 0xFFFFFFF0)

	// v2.5: ThrottleStop BYOVD 通道
	th, err3 := OpenThrottleStop()
	for i := 0; err3 != nil && i < retries; i++ {
		th, err3 = OpenThrottleStop()
		time.Sleep(time.Duration(delayMs) * time.Millisecond)
	}
	if err3 != nil {
		return st
	}
	defer CloseHandle(th)
	st.TSOK = true
	if v, err := TSRead(th, bar0+SS0Offset); err == nil {
		st.SS0, st.SS0OK, st.Unlocked = v, true, v == 0x88888888
	}
	if v, err := TSRead(th, bar0+SS1Offset); err == nil {
		st.SS1 = v
	}
	return st
}

// ScServiceRunning: 查询服务是否 RUNNING (sc.exe query)
// 返回 false 表示查询失败或未运行。
func ScServiceRunning(name string) bool {
	out, err := RunOut("sc.exe", "query", name)
	if err != nil {
		return false
	}
	return strings.Contains(out, "RUNNING") || strings.Contains(strings.ToLower(out), "running")
}
