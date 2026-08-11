# Doctoring: 근거·주장·불확실성 기록

이 디렉터리는 제품 문구와 계산 규칙을 과장 없이 유지하기 위한 연구 기록이다.
`doctoring`은 의료적 진단을 뜻하지 않으며, 이 서비스는 운세를 과학적 예측이나
의사결정 근거로 주장하지 않는다.

## 주장 경계

- 사주·육합·육충·60갑자는 역사·문화적 계산 체계로 설명한다.
- 양력·한국 음력·윤달·절기·시간대는 구현 라이브러리와 한국천문연구원 자료의
  범위 안에서 계산한다. 범위 밖·학파 차이·출생 시각 미상은 불확실성으로 표시한다.
- 두 사람 점수는 저장소의 설명 가능한 정렬 규칙이지 확률, 궁합의 객관적 판정,
  미래 사건의 인과 효과가 아니다.
- RFC 5545/4791은 일정 표현·전송 표준이며 사주 계산의 타당성을 보증하지 않는다.

## APA 7 참고문헌

Aslaksen, H. (2010). *The mathematics of the Chinese calendar*.
https://gwern.net/doc/science/2010-aslaksen.pdf

Homola, S. (2021). Chinese Eight Signs prediction: Ontology, knowledge, and
computation. *Social Analysis, 65*(2). https://doi.org/10.3167/sa.2021.650204

National Institute of Standards and Technology. (2022). *Secure software
development framework (SSDF) version 1.1* (NIST SP 800-218).
https://doi.org/10.6028/NIST.SP.800-218

National Institute of Standards and Technology. (2025). *Secure software
development framework (SSDF) version 1.2* [Draft].
https://csrc.nist.gov/Projects/ssdf/publications

Korea Internet & Security Agency. (n.d.). *클라우드 보안인증제 제도소개*.
https://isms.kisa.or.kr/main/csap/intro/index.jsp

International Organization for Standardization. (2025). *ISO/IEC 27018:2025
Information security, cybersecurity and privacy protection — Guidelines for
protection of personally identifiable information (PII) in public clouds acting
as PII processors*. https://www.iso.org/standard/27018

Internet Engineering Task Force. (2007). *Calendaring extensions to WebDAV
(CalDAV)* (RFC 4791). https://www.rfc-editor.org/rfc/rfc4791

Internet Engineering Task Force. (2009). *Internet calendaring and scheduling
core object specification* (iCalendar) (RFC 5545).
https://www.rfc-editor.org/rfc/rfc5545

박한얼, 민병희, & 안영숙. (2017). 한국 음력의 운용과 계산법 연구.
*천문학논총, 32*(3), 407–414. https://doi.org/10.5303/PKAS.2017.32.3.407

이청하, & 신순옥. (2023). 역법에서의 시진(時辰) 설정에 대한 타당성 논의.
*산업진흥연구, 8*(2), 119–128. https://doi.org/10.21186/IPR.2023.8.2.119

## 조사 운영

표준·라이브러리·보안 통제는 릴리스 전에 공식 원문과 현재 상태를 다시 확인한다.
NIST SP 800-218 Rev. 1.2는 이 문서 작성 시 draft이므로 인증 근거로 사용하지
않는다. Context7·Consensus·Figma 같은 도구가 접근 불가능한 실행에서는 사용한
것처럼 기록하지 않고, 공식 문서와 저장소 테스트로 대체한 사실을 남긴다.
