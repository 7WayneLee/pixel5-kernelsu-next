# Pixel 5 KernelSU Next Builder

[English](README.md)

使用 GitHub Actions 為 Pixel 5 編譯 KernelSU Next 核心。

## 支援資料

| 項目 | 支援設定 |
| --- | --- |
| 裝置 | Google Pixel 5（`redfin`） |
| 系統 | Google 原廠 Android 14 |
| 韌體 | `UP1A.231105.001.B2` |
| 核心 | `4.19.278-g7b0944645172-ab10812814` |
| KernelSU Next | `v3.4.0-legacy-pixel5` · 33306 · UAPI 5 |
| 管理器 | [v3.4.0-29-g3daa5787](https://github.com/KernelSU-Next/KernelSU-Next/actions/runs/37513294225) · 33323 · UAPI 5 |
| 整合方式 | Built-in、manual hooks；保留原廠 CFI/LTO/MODVERSIONS |
| Bootloader | 已解鎖 |
| 驗證狀態 | 已在一部裝置驗證開機與 ADB root，完整硬體測試待完成（[紀錄](docs/validation.md)） |

**管理器相容性：** 使用上方連結中已驗證的 UAPI 5 建置。登入 GitHub 後下載其 `manager` artifact。v3.4.0 正式版 APK（33294、UAPI 4）與此核心不相容。

僅支援上述裝置與原廠韌體。固定來源版本見[核心 profile](profiles/redfin-up1a-231105-001-b2.json)與[管理器 lock](sources/manager.lock.json)。

## GitHub Actions 使用方式

1. Fork 此儲存庫，並在自己的 Fork 啟用 **Actions**。
2. 開啟 **Actions → Build Pixel 5 KernelSU Next → Run workflow**。
3. 選擇 `redfin-up1a-231105-001-b2`，開始執行。
4. 等待核心編譯與 ABI 檢查成功。
5. 開啟成功的 run，在 **Artifacts** 下載 `pixel5-redfin-up1a-231105-001-b2-<run_number>`。

產物包含 `Image.lz4`、ABI 報告、建置資訊與記錄檔。失敗 run 的產物僅供診斷。
