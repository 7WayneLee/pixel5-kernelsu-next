# Pixel 5 KernelSU Next Builder

[![Tooling CI](https://github.com/7WayneLee/pixel5-kernelsu-next/actions/workflows/ci.yml/badge.svg)](https://github.com/7WayneLee/pixel5-kernelsu-next/actions/workflows/ci.yml)

[English](README.en.md)

以 GitHub Actions 為 **Pixel 5（redfin）原廠 Android 14 `UP1A.231105.001.B2`** 編譯 KernelSU Next 核心，再於自己的電腦使用原廠 boot 打包。

**目前為實驗性專案，尚未完成實機開機與 root 驗證。Actions 成功只代表編譯和靜態檢查通過。** 第一個實機測試結果會記錄在 [驗證紀錄](docs/validation.md)。

[首個成功建置](https://github.com/7WayneLee/pixel5-kernelsu-next/actions/runs/37741524948) 已完成原廠與 Next 編譯、9,115 個匯出符號 CRC 比對，以及本機 218 個原廠 vendor_boot 模組的檢查。

## 支援範圍

| 項目 | 目前支援 |
| --- | --- |
| 裝置 | Pixel 5 / redfin |
| 系統 | Google 原廠 Android 14，UP1A.231105.001.B2 |
| 原廠核心 | 4.19.278-g7b0944645172-ab10812814 |
| Next 原始碼 | legacy 分支固定 commit，見 profiles/ |
| 整合方式 | built-in + manual hooks，保留原廠 CFI/LTO/MODVERSIONS |
| bootloader | 必須已解鎖 |
| 其他 ROM / Pixel 4a 5G / Pixel 5a | 目前沒有相容性承諾，工具會拒絕其他映像 |

## 使用 GitHub Actions

1. Fork 此儲存庫，在自己的 Fork 啟用 Actions。
2. 開啟 **Actions → Build Pixel 5 KernelSU Next → Run workflow**。
3. 選擇 `redfin-up1a-231105-001-b2`，開始編譯。
4. 工作流程會先編譯原廠基準，再編譯 Next，比較所有原有匯出符號的 CRC。
5. 只有成功的 run 可用來打包；下載該 run 的 `pixel5-...` artifact，解壓至 `artifacts/`。

大型核心編譯可能需要較長時間。若 run 失敗，artifact 可能仍包含診斷檔，不能當成可刷入產物。專案不會自動發布 Release 或操作手機。

## 在自己的電腦打包 boot

需要 Python 3.11+ 和 lz4。macOS 可以執行 `brew install lz4`；Linux 可以執行 `sudo apt install lz4`。

從 [Google factory images](https://developers.google.com/android/images#redfin) 取得同一版本，將 `boot.img` 和 `vendor_boot.img` 複製至自己的資料夾並命名為：

```text
stock-boot/
  stock-boot.img
  stock-vendor_boot.img
```

在專案根目錄執行（換成你自己的路徑；輸出資料夾必須尚未存在）：

```bash
python3 tools/pack_boot.py \
  --stock-dir "/path/to/stock-boot" \
  --artifact-dir "/path/to/artifacts" \
  --output-dir "/path/to/patched"
```

工具會核對原廠映像 SHA-256、產物雜湊、基準與 Next ABI，並讀取原廠 `vendor_boot` 內所有核心模組的 vermagic 和匯入符號 CRC。只要不相容就停止，不會提供「忽略檢查」選項。

輸出包含 `boot-redfin-up1a-231105-001-b2-ksun.img`、校驗檔及打包紀錄。只替換 boot 內的核心，保留原廠 ramdisk；原廠 `vendor_boot`、DTB 與 dtbo 都保留。原 boot 的 AVB 簽章不再適用，因此打包時移除其舊 AVB metadata，僅供已解鎖的 bootloader 使用。

**原廠映像不會被覆寫，也不會上傳到 GitHub。**

## 首次測試

先安裝 [官方 KernelSU Next Manager v3.4.0](https://github.com/KernelSU-Next/KernelSU-Next/releases/tag/v3.4.0)。本專案沒有變更官方管理器簽章，也沒有加入 SUSFS。

保留原廠 boot 備份，先使用暫時開機：

```bash
adb reboot bootloader
fastboot getvar product
fastboot getvar current-slot
fastboot boot /path/to/patched/boot-redfin-up1a-231105-001-b2-ksun.img
```

確認裝置是 `redfin`，Next 管理器顯示已運作，再測試 root 授權、Wi-Fi、行動網路、相機、觸控、音訊、藍牙與重啟。`su` 驗證可以執行 `adb shell su -c id`，在管理器授權 Shell，應看到 `uid=0`。

**尚未通過這些實機檢查前，不要永久刷入。** 暫時開機失敗時，回到 bootloader 重新啟動，便會回到尚未變更的原廠 boot。

確認正常後，回到 bootloader 再確認目前槽位，刷入同一個目前槽位：

```bash
fastboot flash boot /path/to/patched/boot-redfin-up1a-231105-001-b2-ksun.img
fastboot reboot
```

若需要還原，在相同槽位執行：

```bash
fastboot flash boot /path/to/stock-boot/stock-boot.img
fastboot reboot
```

此流程不需要清除資料、重新解鎖、同時刷兩個槽位或重新鎖定 bootloader。系統版本改變後，需要新的 profile 與重新驗證。

## 維護與新增支援

所有 Google 來源固定在 [source lock](sources/google.lock.json)，Next 固定在 [profile](profiles/redfin-up1a-231105-001-b2.json)。不會在編譯中自動跟隨最新分支。Next hooks 簽名已依固定原始碼核對；官網範例目前部分簽名較舊。

Next 的 Kbuild 原本會在 4.19 `struct seccomp` 加入新欄位；本 profile 仍使用 `put_seccomp_filter()`，不需要該欄位。對應 patch 移除這項自動 backport，以維持原廠模組 ABI。後續升級必須重新檢查此假設以及完整 ABI 比對。

新增機型或韌體前，必須提供相符 source lock、原廠 config、stock 映像雜湊與 hooks，重新完成編譯、模組 CRC 和實機檢查。不能只改 device 名稱或改下載連結。

執行工具測試：

```bash
python3 -m unittest discover -s tests -v
```

Linux x86_64 本機編譯指令見 [維護說明](docs/development.md)。回報問題時提供 workflow run 網址、韌體版本與檢查報告，請勿上傳 token 或完整個人資料。

## 授權與來源

本專案自有 Python、workflow 與文件使用 MIT；Linux config 與 Linux/Next 衍生 patches 使用 GPL-2.0-only。上游核心、Next、工具鏈各自遵循原有授權，詳見 [NOTICE](NOTICE.md)。

來源：[Google stock kernel](https://android.googlesource.com/kernel/msm/+/7b0944645172)、[KernelSU Next](https://github.com/KernelSU-Next/KernelSU-Next)、[Next 非 GKI 指南](https://kernelsu-next.github.io/webpage/pages/how-to-integrate-for-non-gki.html)。
