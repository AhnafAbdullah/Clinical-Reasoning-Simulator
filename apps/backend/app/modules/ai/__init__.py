"""AIOS — the AI Operating System (Vol 4A).

Every AI operation in the platform goes through the AIOS. No other module talks
to a provider directly. Components each own exactly one responsibility:
Context Builder, Memory Manager, Model Router, Validator, Retry Manager, Stream
Manager, Metrics Collector, Audit Logger — wired together by ``aios.AIOS``.
"""
