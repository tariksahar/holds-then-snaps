# Kavramlar — sade karşılıklar

Bu projede geçen her terimin gündelik dille açıklaması. Rapor yazarken de
işe yarar: bir şeyi buradaki gibi anlatamıyorsan, muhtemelen henüz tam
oturmamıştır.

---

## 1. Oyunun kendisi

**Mahkum İkilemi (Prisoner's Dilemma)**
İki kişi aynı anda iki seçenekten birini seçiyor: işbirliği yapmak veya
ihanet etmek. İkisi de işbirliği yaparsa ikisi de iyi durumda olur. Ama
tek başına ihanet eden, işbirliği yapanı sömürüp daha da fazlasını
kazanır. Herkes bunu düşününce ikisi de ihanet eder ve ikisi de kaybeder.
İkilem burada: *bireysel olarak akıllıca olan şey, ortaklaşa aptalca.*

**Tekrarlı Mahkum İkilemi (Iterated Prisoner's Dilemma, IPD)**
Aynı iki kişi bu oyunu bir kez değil, arka arkaya yüzlerce kez oynuyor.
Bu her şeyi değiştirir: artık karşındakinin geçmişini biliyorsun ve
bugün yaptığın şeyin yarın sana döneceğini biliyorsun. İşbirliği ancak
bu tekrar sayesinde mümkün hale gelir.

**C ve D**
C = Cooperate = işbirliği. D = Defect = ihanet. Kod boyunca hep bu iki
harf geçecek.

**T, R, P, S — dört kazanç değeri**
Her turda ne kazandığını belirleyen dört sayı:

| Harf | Açılımı | Ne zaman alırsın | Değerimiz |
|---|---|---|---|
| **T** | Temptation (ayartma) | Sen ihanet, o işbirliği | 5 |
| **R** | Reward (ödül) | İkiniz de işbirliği | 3 |
| **P** | Punishment (ceza) | İkiniz de ihanet | 1 |
| **S** | Sucker (enayi) | Sen işbirliği, o ihanet | 0 |

**`T > R > P > S`**
Bu sıralama oyunu "mahkum ikilemi" yapan şeydir. Sömürmek en kârlı,
sömürülmek en kötü, ortaklaşa iyi olmak ortaklaşa kötü olmaktan iyi.
Bu sıra bozulursa oyun başka bir oyuna dönüşür.

**`2R > T + S`**
İkinci şart. Şunu garantiler: sırayla sömürüşmek (bir tur sen beni
kandır, bir tur ben seni) karşılıklı işbirliğinden daha kârlı olmasın.
Bizim sayılarla: 2×3 = 6, 5+0 = 5. Sağlanıyor ama kıl payı — bu yüzden
ilginç bir test noktası.

**Kazanç matrisi (payoff matrix)**
Kimin kime karşı ortalama kaç puan aldığını gösteren tablo. Satırlar ve
sütunlar stratejiler. Turnuvanın asıl ürünü sıralama değil bu tablodur,
çünkü evrim aşaması doğrudan bunu kullanacak.

**Tur başına ortalama vs. toplam**
Bir maç 200 tur sürüyorsa toplam puan 600 olabilir, tur başına ortalama
3'tür. Evrim aşamasının **ortalamayı** kullanması gerekiyor — toplamı
kullanırsak maç uzunluğu sonuçları kaydırır. Bizim ilk kritik kontrol
noktamız tam olarak bu.

---

## 2. Stratejiler

Her strateji basit bir kural. Hiçbiri öğrenmiyor, hepsi elle yazılmış.

- **Always Cooperate (AllC)** — Ne olursa olsun işbirliği. Saf iyi niyet.
- **Always Defect (AllD)** — Ne olursa olsun ihanet. Saf bencillik.
- **Tit-for-Tat (TFT)** — "Kısasa kısas". İlk turda işbirliği, sonra
  rakibin bir önceki hamlesini aynen tekrarla. Kin tutmaz, hemen affeder.
  Axelrod'un turnuvasını kazanan strateji.
- **Grim Trigger** — "Bir kere yaparsan biter". Baştan işbirliği, ama
  rakip *bir kez* bile ihanet ederse sonsuza kadar ihanet. Asla affetmez.
- **Random** — Yazı tura. Kıyas noktası olarak var; bir strateji bundan
  kötüyse gerçekten kötüdür.
- **Pavlov (Win-Stay, Lose-Shift)** — "Kazanıyorsan devam et,
  kaybediyorsan değiştir". Rakibin ne yaptığına değil, *kendi aldığı
  sonuca* bakar. İyi puan aldıysa aynı hamleyi tekrarlar, kötü aldıysa
  hamlesini değiştirir. Hata yapan dünyalarda güçlü olmasının sebebi bu.
- **Tit-for-Two-Tats (TF2T)** — TFT'nin sabırlı hali. Misilleme için
  rakibin *iki kez üst üste* ihanet etmesini bekler.
- **Generous Tit-for-Tat (GTFT)** — TFT'nin affedici hali. İhanete
  genelde misilleme yapar ama belli bir ihtimalle görmezden gelir.

---

## 3. Evrim kısmı

**Popülasyon payı**
Kalabalığın yüzde kaçının şu stratejiyi oynadığı. Yedi stratejimiz varsa
ve hepsi eşit paydaysa, her birinin payı 1/7. Payların toplamı her zaman
1 olmak zorunda — bu bir hata kontrolü olarak da kullanılıyor.

**Uygunluk (fitness)**
Bir stratejinin mevcut kalabalığa karşı aldığı ortalama puan. "Bu
kalabalığın içinde bu stratejiyi oynasam ne kazanırım" sorusunun cevabı.
Biyolojiden ödünç alınmış bir kelime; burada "başarı" demek.

**Replikatör dinamiği (replicator dynamics)**
Popülasyonun nesilden nesile nasıl değiştiğini söyleyen kural. Tek
cümlesi şu: **ortalamadan iyi iş çıkaran stratejinin payı büyür,
ortalamanın altında kalanın payı küçülür.** Formülü de aynı şeyi söyler:
yeni pay = eski pay × (kendi puanı ÷ ortalama puan). Oranı 1'den büyükse
büyür, küçükse küçülür.

**Nesil (generation)**
Bu güncellemenin bir kez uygulanması. 200 nesil = kuralı 200 kez arka
arkaya çalıştırmak.

**İyi karışmış popülasyon (well-mixed)**
Herkesin herkesle eşit ihtimalle karşılaştığı varsayımı. Kimsenin
komşusu, mahallesi, sosyal ağı yok. Gerçekçi değil ama modeli basit
tutuyor — v1'de bilinçli tercih.

**Seçilim şiddeti (selection intensity)**
Puan farklarının payları ne kadar hızlı değiştirdiğini ayarlayan kadran.
Yüksekse küçük bir puan üstünlüğü bile hemen ezici üstünlüğe dönüşür,
düşükse her şey yavaş yavaş olur. Neden gerekli: formül puanların mutlak
büyüklüğüne duyarlı — bütün puanlara 100 eklesen sonuç aynı yere gider
ama *kaç nesilde* gittiği tamamen değişir. Rapor "50. nesilde tükendi"
diyecekse bu kadranın kaça ayarlandığını söylemek zorunda.

**Yok olma eşiği (extinction threshold)**
Matematiksel olarak bir pay hiçbir zaman tam sıfır olmaz, sonsuza kadar
küçülür (0.0000001, sonra 0.00000001...). "Bu strateji artık öldü"
diyebilmek için bir kesme noktası seçmek gerekiyor. Keyfi bir seçim,
o yüzden açıkça yazılması gereken bir seçim.

**Simpleks (simplex)**
Bütün olası popülasyon karışımlarının kümesi. Üç strateji varsa bunu bir
üçgen olarak çizebilirsin: köşeler "herkes tek bir stratejiyi oynuyor"
durumları, ortası karışım. Üçgen üzerinde ok çizerek "buradan
başlarsan şuraya gidersin" haritası çıkarılabiliyor — çok etkileyici
bir görsel.

**Çekim havzası (basin of attraction)**
Hangi başlangıç karışımlarının aynı sona vardığı. "Nereden başlarsan
işbirliği kazanır, nereden başlarsan ihanet kazanır" sorusunun cevabı.

**ESS — Evrimsel Kararlı Strateji (Evolutionarily Stable Strategy)**
Bir popülasyonun tamamı bu stratejiyi oynuyorsa, içeri sızan küçük bir
azınlık grubun onu deviremediği strateji. "Yerleşik ve devrilemez"
demek.

**Nötr sürüklenme (neutral drift)**
Bir stratejinin, yerleşik stratejiye karşı ne kazanıp ne kaybetmemesi —
yani berabere kalması. Berabere kaldığı için cezalandırılmaz, sessizce
çoğalabilir. Tehlikeli olan kısım şu: çoğaldıktan sonra kapıyı üçüncü
bir stratejiye açar.

**İstila (invasion)**
Küçük bir azınlığın, yerleşik çoğunluğa karşı avantaj bulup payını
büyütmesi.

> Bu üçü birlikte projenin en güzel bulgusunu veriyor: TFT kazanır, ama
> AllC ona karşı berabere kaldığı için bedavaya içeri sızar (nötr
> sürüklenme), AllC yeterince çoğalınca da AllD onları sömürerek istila
> eder. Yani zirve kalıcı değil. Tekrarlı mahkum ikileminde hiçbir saf
> strateji ESS değildir.

---

## 4. Deneyin iki kadranı

**ε (epsilon) — hata payı**
Ajanın istemediği hamleyi oynama ihtimali. İşbirliği yapacaktı, eli
kaydı, ihanet etti. Gerçek hayatta herkes hata yapar; modelde hata yoksa
model gerçek hayattan çok daha affedici bir dünyayı anlatıyor demektir.

- **Uygulama hatası (execution error):** Sen yanlış hamleyi oynadın ve
  bunu biliyorsun.
- **Algı hatası (perception error):** Rakip işbirliği yaptı ama sen
  ihanet gördün. Artık ikiniz aynı maçı farklı hatırlıyorsunuz.

**w — süreklilik olasılığı / "geleceğin gölgesi"**
Oyunun bir tur daha devam etme ihtimali. w yüksekse taraflar "bu adamla
daha çok işim var" diye düşünür ve işbirliği mantıklı hale gelir. w
düşükse "nasılsa bitiyor" der ve sömürür.

**Geriye dönük tümevarım (backward induction)**
Neden sabit tur sayısının sorun olduğunu açıklayan akıl yürütme: 200.
tur son turdur, ceza ihtimali yoktur, o yüzden ihanet et. Bunu ikimiz de
bildiğimize göre 199. tur da fiilen son turdur, orada da ihanet et. Zincir
geriye doğru işleyerek en başa kadar gider ve "hiç işbirliği yapma"
sonucu çıkar. Tur sayısını belirsiz yaparak (w ile) bu zinciri kırıyoruz.

**Faz haritası (phase diagram)**
İki kadranı yatay ve dikey eksene koyup her noktayı "burada kim hayatta
kaldı" bilgisine göre renklendiren harita. Projenin hedeflediği tek
büyük görsel bu.

**Mutasyon / göç terimi**
Tükenmiş stratejilerin çok küçük oranlarda geri sızmasına izin veren
ekleme. Hem gerçekçi (kimse tamamen yok olmaz) hem de teknik bir sorunu
çözüyor: saf replikatör dinamiğinde bir kez tükenen asla geri gelemez.

---

## 5. Proje jargonu

**Round-robin turnuva**
Herkesin herkesle oynadığı format. Lig usulü. Kendi kendine oynanan maç
da dahil — çünkü evrimde bir stratejinin kendi kopyalarıyla karşılaşması
gerçekten oluyor.

**Seed (tohum)**
Rastgele sayı üretecinin başlangıç değeri. Aynı tohumu verirsen aynı
"rastgele" diziyi alırsın. Kodu yarın tekrar çalıştırdığında aynı
sonucu alman bunun sayesinde.

**Değişmez (invariant)**
Kod doğruysa *her zaman* doğru olması gereken ifade. Örnek: payların
toplamı 1. Testler bunları kontrol eder — hata olduğunda çıktıya
bakarak anlayamayacağın şeyleri yakalarlar.

**Karar günlüğü (decision log)**
Verilen her metodolojik seçimin, sebebinin ve reddedilen alternatifin
kaydı. Hem çalışmanın dürüstlük belgesi hem de teslim edilecek bir
çıktı.

**Faz A / B / C**
A = turnuva (bilineni üret, koda güven kazan). B = evrim (popülasyon
nasıl değişiyor). C = asıl deney (iki kadranı tara, haritayı çıkar).

---

## 6. Sonuçları okurken

**Bu bir düello değil**
En sık yapılan hatalı okuma bu. Bir maçta rakibinden *daha fazla* puan almak
diye bir hedef yok. Sen kendi puanını topluyorsun, o kendi puanını topluyor.
İkiniz de 3.00 alabilirsiniz (sürekli işbirliği) ya da ikiniz de 1.00
alabilirsiniz (sürekli ihanet). Birinin kazanması için diğerinin kaybetmesi
gerekmiyor — oyunun bütün mesele buradan çıkıyor.

Somut kanıt: Kısasa Kısas hiçbir maçta rakibinden fazla puan alamaz. İlk
ihaneti asla o başlatmadığı için en iyi ihtimalle berabere kalır. Buna rağmen
Axelrod'un turnuvasını kazandı. Çünkü önemli olan tek bir maçı "yenmek" değil,
herkese karşı toplamda iyi puan biriktirmek.

**Puanları neye göre okumalı**
Tur başına ortalama puanın üç doğal kıyas noktası var:

| Değer | Anlamı |
|---|---|
| **5.00** | Kesintisiz sömürü — hep sen ihanet, o hep işbirliği |
| **3.00** | Sürekli karşılıklı işbirliği. Sürdürülebilir en iyi sonuç |
| **1.00** | Sürekli karşılıklı ihanet. İkiliğin herkesi çektiği dip |
| **0.00** | Kesintisiz enayilik — hep sen işbirliği, o hep ihanet |

3.00'ün üstüne çıkmak, birilerini sömürmüş olmak demektir. 1.00'in altına
düşmek, sömürülmüş olmak demektir. Aradaki her sayı bu ikisinin karışımı.

**Sömürmek her zaman kazandırmaz**
Acımasız Tetik, Yazı Tura'ya karşı 2.75 alıp onu 0.75'e düşürebilir. Ama aynı
Acımasız Tetik, Hep İhanet'e karşı 0.995'te kalır. Bir stratejinin değeri tek
bir rakibe karşı ne yaptığı değil, bütün kalabalığa karşı ne yaptığıdır — ve
turnuva sıralaması da tam olarak bu yüzden kadroya bu kadar bağlı (bkz. D-010).
