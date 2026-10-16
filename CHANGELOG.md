# 📋 NovaCare System Care Suite - Sürüm Güncelleme Notları (Changelog)

Tüm önemli değişiklikler, yeni özellikler, hata düzeltmeleri ve optimizasyonlar bu belgede kronolojik olarak kayıt altına alınmaktadır.

---

## 🚀 [v1.0.1] - 2026-10-16

### 🎨 Arayüz, Pencere Boyutu ve Yazı Optimizasyonları
* **Dinamik Duyarlı (Responsive) Geometri:** Ana pencere boyutu sabit `1180x780` pikselden, kullanıcının monitör çözünürlüğünü ve görev çubuğu payını (`availableGeometry`) otomatik okuyan dinamik hesaplamaya geçirildi. 1366x768 ekranlarda ve %125 / %150 Windows DPI ölçeklemesinde pencerenin görev çubuğu arkasına taşması engellendi.
* **Kelime Kaydırma (Word-Wrap) Desteği:** 11 sekmenin tamamındaki alt başlık, açıklama ve durum etiketlerine `setWordWrap(True)` uygulandı. Türkçe metinlerin pencere daralsa dahi kesilmesi veya yatayda taşması önlendi.
* **Ana Panel (Dashboard) Scroll Desteği:** Dashboard görünümü çerçevesiz, modern `QScrollArea` içerisine alınarak küçük ekranlarda kartların ve butonların kaybolması engellendi.
* **Dairesel Sağlık Göstergesi:** `CircularHealthGauge` boyutu `220x220`'den `185x185`'e optimize edilerek dikey alan rahatlatıldı.
* **Gezinti Menüsü (Sidebar):** Menü genişliği 240px'e, buton dolguları `9px 14px`'e çekilerek 11 menü maddesi ve yönetici durumu rozeti hiçbir dikey kaydırmaya gerek kalmadan tam sığdırıldı.

---

### 🛡️ Kurulum Sihirbazı & Denetim Masası Kaldırma Sistemi
* **Entegre Yerel Kaldırma Motoru (`NovaCare.exe --uninstall`):** Uygulamanın çekirdeğine yerel kaldırma sihirbazı eklendi. Windows Denetim Masası veya Windows 10/11 Ayarlar > Yüklü Uygulamalar ekranından "Kaldır" butonuna basıldığında modern koyu temalı onay penceresiyle program, başlangıç görevleri, kısayollar ve kayıt defteri anahtarları eksiksiz kaldırılır.
* **Onarılan `uninstall.bat`:** Batch scriptindeki çok satırlı tırnak sözdizimi hataları giderildi; doğrudan yerel `reg delete` komutlarıyla güçlendirildi.
* **Kurulum Sihirbazı Tasarım Yenilemesi:**
  * `QWizard.ClassicStyle` ve tüm pencereyi kapsayan yekpare koyu tema (`#0A0F1D`) uygulandı.
  * Kart yapısındaki CSS miras hatası (`inheritance`) giderildi; yazıların 2 piksele sıkışması, etiketlerin etrafında istenmeyen çerçeveler oluşması ve beyaz zemin üzerine beyaz yazı kontrast sorunu tamamen çözüldü.
  * Sihirbaz boyutu `700x520` piksele çıkarılarak ferah bir görünüm sağlandı.

---

### ⚙️ Yönetici İzinleri ve Derin Temizlik Vurgusu
* **Ayarlar'dan Yönetici Olarak Başlatma:** Ayarlar sekmesine tek tıkla uygulamayı UAC yönetici ayrıcalığı ile yeniden başlatma butonu eklendi.
* **Yönetici Derin Temizlik Vurgusu:** Standart kullanıcı modunda çalışırken temizleme ekranlarında ve bildirimlerde yönetici izinlerinin sistem çöp dosyalarını ve kilitli kayıtları çok daha derinlemesine temizleyebileceği vurgusu yapıldı.

---

### 🔒 Güvenlik & Token Şifreleme
* **Windows DPAPI Şifrelemesi:** GitHub API güncelleme belirteçleri ve hassas yapılandırma verileri Windows DPAPI (`CryptProtectData` / `CryptUnprotectData`) algoritması ile şifrelenerek yetkisiz erişimlere karşı koruma altına alındı.

---

### 🐞 Hata Düzeltmeleri ve Kararlılık
* **Ayarlar Görünümü Eksik Import Düzeltmesi:** `ui/views/settings_view.py` içerisindeki `os` ve `sys` modül eksiklikleri giderilerek açılışta meydana gelen çökme engellendi.
* **Emoji ve Yazı Tipi Render Düzeltmesi:** Windows üzerinde kare kutu şeklinde bozuk çıkan emojiler için font yığınına `Segoe UI Emoji` eklendi.
* **Yol ve Karakter Standardizasyonu:** Türkçe karakterler ve boşluklu Windows kullanıcı dizinlerinde (`OneDrive`, `Kullanıcı Adı`) dosya erişim hataları giderildi.

---

## 📦 [v1.0.0] - 2026-10-15 (İlk Kararlı Sürüm)
* **Tek Tıkla Sistem Bakımı (Dashboard):** Tek tıkla çöp dosya, geçici veri, kayıt defteri ve başlangıç öğelerini tek seferde tarayıp temizleme.
* **Gereksiz Dosya Temizleyici:** Windows Temp, Prefetch, Crash Dumps, MiniDumps, Loglar, Tarayıcı Önbellekleri (Chrome, Edge, Firefox, Brave, Opera, Vivaldi), Küçük Resim Önbelleği temizliği.
* **Kayıt Defteri Onarımı:** Eksik paylaşılan DLL'ler, geçersiz dosya uzantıları, eski yazılım kalıntıları, geçersiz Başlat Menüsü girdileri, Help dosyaları temizliği ve otomatik kayıt defteri yedeği (`.reg`).
* **Başlangıç Yöneticisi:** Windows açılışını yavaşlatan program ve servislerin yönetimi ve gecikmeli başlatma.
* **Program Kaldırıcı:** Kalıntı taraması yapan modern yazılım kaldırma modülü.
* **RAM & Süreç Yöneticisi:** `EmptyWorkingSet` ile bellek sıkıştırma ve arka plan süreç optimizasyonu.
* **Disk Alanı Analizi:** Sürücü kullanım oranları ve en çok yer kaplayan büyük dosyaların tespiti.
* **Gizlilik ve Bloatware Temizliği:** Telemetri kapatma, gereksiz Windows 10/11 yerleşik uygulamalarını kaldırma.
* **Ağ ve DNS Optimize Edici:** TCP/IP ve Winsock sıfırlama, DNS önbelleği temizleme ve en hızlı DNS sunucusuna geçiş.
* **Kurtarma Merkezi:** Sistem Geri Yükleme Noktası oluşturma ve kayıt defteri yedeklerinden geri yükleme.
