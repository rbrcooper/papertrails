# ESMA Data Collection Workflow

## Sequence Diagram

```mermaid
sequenceDiagram
    participant User
    participant RunWorkflow
    participant ESMAWorkflow
    participant ProcessManager
    participant DatabaseManager
    participant PDFProcessor
    participant ESMAWebsite
    participant FileSystem

    User->>RunWorkflow: Execute run_workflow.py
    RunWorkflow->>ESMAWorkflow: Initialize workflow
    
    Note over ESMAWorkflow: Initialize components:<br/>- Database<br/>- WebDriver<br/>- Directories
    
    loop For each company
        ESMAWorkflow->>ProcessManager: Process company
        ProcessManager->>DatabaseManager: Get/Create issuer
        
        loop For each bond
            ProcessManager->>ESMAWebsite: Search bonds by LEI
            ESMAWebsite-->>ProcessManager: Return bond data
            
            ProcessManager->>DatabaseManager: Get/Create bond
            
            loop For each document
                ProcessManager->>ESMAWebsite: Get document URL
                ESMAWebsite-->>ProcessManager: Return document URL
                
                ProcessManager->>PDFProcessor: Process document
                PDFProcessor->>ESMAWebsite: Download PDF
                ESMAWebsite-->>PDFProcessor: Return PDF
                
                PDFProcessor->>FileSystem: Save PDF
                PDFProcessor->>DatabaseManager: Store document metadata
            end
        end
        
        ProcessManager->>FileSystem: Generate company report
    end
    
    ESMAWorkflow->>FileSystem: Generate final reports
    ESMAWorkflow->>DatabaseManager: Validate data
    ESMAWorkflow-->>User: Return completion status
```

## Component Interactions

### 1. Initialization Phase
- User runs `run_workflow.py`
- `ESMAWorkflow` initializes all components
- Sets up database, WebDriver, and directories

### 2. Company Processing Phase
- For each company in configuration:
  1. Get/Create issuer in database
  2. Search for bonds on ESMA website
  3. Process each bond found

### 3. Bond Processing Phase
- For each bond:
  1. Validate bond data
  2. Store in database
  3. Collect associated documents

### 4. Document Processing Phase
- For each document:
  1. Download PDF from ESMA
  2. Save to file system
  3. Store metadata in database

### 5. Reporting Phase
- Generate company-specific reports
- Create final workflow summary
- Validate collected data

## Data Flow

```mermaid
graph TD
    A[ESMA Website] -->|Bond Data| B[Process Manager]
    B -->|Store| C[Database]
    A -->|PDF Documents| D[PDF Processor]
    D -->|Save| E[File System]
    D -->|Metadata| C
    B -->|Reports| F[Financial Data]
```

## Component Responsibilities

### RunWorkflow
- Entry point
- Error handling
- Process initialization

### ESMAWorkflow
- Main workflow orchestration
- Component coordination
- Status tracking

### ProcessManager
- Company processing
- Bond data collection
- Report generation

### DatabaseManager
- Data persistence
- Record management
- Data validation

### PDFProcessor
- Document downloading
- PDF processing
- File management

### FileSystem
- PDF storage
- Report storage
- Data organization 