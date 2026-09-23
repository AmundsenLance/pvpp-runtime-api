# PV-PP Framework Version 2.1 --- Documentation Guide

This directory contains the **current PV-PP Version 2.1 public
documentation set**. The numbered documents are arranged in a
recommended reading and working order. They are not "volumes" and do not
need to be read sequentially for every use case.

## Where to Start

-   **New to PV-PP?** Start with **01**.
-   **Need the architecture?** Read **02--03**.
-   **Building a model or application?** Use **04**.
-   **Writing software against the runtime?** Use **05**.
-   **Comparing PV-PP with established theory?** Use **06**.
-   **Building or evaluating benchmarks?** Use **07--09**.

## Current Documentation Set

  -----------------------------------------------------------------------
  No.               Document          Primary purpose   Document class
  ----------------- ----------------- ----------------- -----------------
  **01**            **PVPP --- What   Accessible        External
                    Is It And What Is introduction to   explanation /
                    It Good For?**    PV-PP, its        orientation
                                      purpose, scope,   
                                      and principal     
                                      distinctions.     

  **02**            **PVPP Framework  Technical         External review /
                    Executive         overview for      orientation
                    Overview**        serious readers   
                                      and external      
                                      reviewers,        
                                      including         
                                      maturity,         
                                      evidence,         
                                      limitations, and  
                                      open research     
                                      questions.        

  **03**            **PVPP Compact    Compact           Supporting
                    Architecture      whole-system map  architecture
                    Skeleton**        of actual state,  summary
                                      perceived state,  
                                      objectives,       
                                      decision          
                                      architecture,     
                                      execution,        
                                      Layer-1           
                                      transition, and   
                                      supporting        
                                      governance        
                                      surfaces.         

  **04**            **PVPP Scenario   Primary guide for Modeling guidance
                    and Model         translating a     
                    Architecture      real or           
                    Guide**           hypothetical      
                                      domain into a     
                                      valid PV-PP       
                                      model.            

  **05**            **PVPP Runtime    Developer         Runtime
                    API Reference**   reference for the implementation
                                      frozen PV-PP      reference
                                      Runtime V2.1      
                                      successor         
                                      baseline, v0.141. 

  **06**            **PVPP Structural Bounded           Theory /
                    Comparison and    comparison with   positioning
                    Theoretical       established       
                    Positioning**     decision,         
                                      control,          
                                      game-theoretic,   
                                      viability, and    
                                      safety-oriented   
                                      approaches.       

  **07**            **PVPP Benchmark  Converts a valid  Benchmark design
                    Design Guide**    PV-PP             guidance
                                      scenario/model    
                                      into a controlled 
                                      benchmark,        
                                      simulation, or    
                                      experimental      
                                      specification.    

  **08**            **PVPP Benchmark  Converts a        Implementation /
                    Programming and   benchmark         benchmark
                    Runtime           specification     guidance
                    Integration       into executable   
                    Guide**           software and      
                                      explains when and 
                                      how to integrate  
                                      Runtime V2.1.     

  **09**            **PVPP Safe       Narrow teaching   Evidence /
                    Margin vs Fast    example           teaching example
                    Gain Gridworld    separating        
                    Teaching          visible           
                    Benchmark**       task/reward       
                                      success from      
                                      viability margin, 
                                      recovery, and     
                                      false success.    
  -----------------------------------------------------------------------

## Recommended Reader Paths

**General reader**\
01 → 02 → 03

**Researcher or reviewer**\
01 → 02 → 03 → 06, then the relevant modeling, benchmark, proof, or
research materials.

**Application/model developer**\
01 → 03 → 04

**Software developer**\
01 → 03 → 04 → 05

**Benchmark developer**\
01 → 03 → 04 → 07 → 08 → 09

The paths are recommendations, not authority relationships.

## Authority and Scope

The public documentation set contains several different kinds of
documents. They should not be treated as interchangeable sources of
authority.

-   **Framework authority:** Current Framework Version 2.1 owner
    specifications control canonical PV-PP framework meaning.
-   **Runtime authority:** Frozen Runtime V2.1 v0.141 source and tests
    control implemented runtime behavior. The Runtime API Reference
    explains that implementation but does not redefine the framework.
-   **Modeling and benchmark guidance:** Documents 04, 07, and 08
    explain how to construct models and tests without creating new
    canonical operators or doctrine.
-   **External explanation and positioning:** Documents 01, 02, 03, and
    06 explain, summarize, or position the framework; they do not
    supersede owner specifications.
-   **Teaching/evidence examples:** Document 09 demonstrates a bounded
    proposition and is not validation of the complete framework.

## Framework and Runtime Must Remain Distinct

PV-PP Framework Version 2.1 and Runtime V2.1 are related but not
identical.

The framework defines the architecture and permits application/runtime
implementations consistent with that architecture. The current frozen
runtime, **v0.141**, implements a substantial synchronous subset and
passed its frozen **1093/1093 regression suite**.

Runtime v0.141 **does not provide asynchronous sensing, external
instrumentation hooks, or autonomous in-flight environment-change
detection**. Applications may provide instrumentation and state/evidence
updates around the runtime, but those capabilities must not be
attributed to v0.141 itself.

## Versioning and Historical Material

The numbered files in this directory are the **current Version 2.1
documentation set**.

Earlier documentation has been moved to **Pre-v2.1 Consolidation
Material** and related archive locations. Those files preserve
provenance, prior formulations, and development history. They are not
current documentation and should not be used to override the Version 2.1
framework, frozen v0.141 runtime, or the current documents listed above.

The former "Volume One through Volume Six" organization is retired. The
**01--09 prefixes indicate navigation/reading order only**; they do not
create a new volume system or imply that every reader must read every
document.

## Suggested Citation / Identification Practice

When referring to a document, identify its title and Version 2.1 status
rather than calling it "Volume 1," "Volume 2," and so on. When
implementation behavior matters, also identify the runtime version,
currently frozen **Runtime V2.1 v0.141**.

------------------------------------------------------------------------

**Current documentation baseline:** PV-PP Framework Version 2.1\
**Current frozen runtime baseline:** PV-PP Runtime V2.1 v0.141\
**Documentation sequence:** 01--09\
**Historical documentation:** retained separately as pre-Version-2.1
consolidated/archive material
