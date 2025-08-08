"""
Batch Processing Performance Test Suite
======================================
Performance tests for batch processing operations.
"""

import sys
import os
import time
import statistics
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import json

# Add project root to sys.path to allow importing from processes
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from processes.pdf_extractor import PDFExtractor


class TestBatchProcessing:
    """Performance tests for batch processing operations."""
    
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
        self.logger = self._setup_logging()
        self.extractor = PDFExtractor(debug_mode=debug_mode)
    
    def _setup_logging(self):
        """Configure logging."""
        level = logging.DEBUG if self.debug_mode else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        return logging.getLogger('TestBatchProcessing')
    
    def benchmark_single_pdf_processing(self, pdf_path: str, iterations: int = 5) -> Dict[str, Any]:
        """Benchmark single PDF processing performance."""
        self.logger.info(f"Benchmarking single PDF processing: {pdf_path} ({iterations} iterations)")
        
        if not os.path.exists(pdf_path):
            return {'success': False, 'error': f'PDF file not found: {pdf_path}'}
        
        times = []
        results = []
        
        for i in range(iterations):
            start_time = time.time()
            
            try:
                result = self.extractor.process_single_pdf(pdf_path)
                end_time = time.time()
                
                processing_time = end_time - start_time
                times.append(processing_time)
                results.append(result is not None)
                
                self.logger.debug(f"Iteration {i+1}: {processing_time:.2f}s")
                
            except Exception as e:
                self.logger.error(f"Error in iteration {i+1}: {e}")
                results.append(False)
        
        if not times:
            return {'success': False, 'error': 'No successful processing times recorded'}
        
        # Calculate statistics
        avg_time = statistics.mean(times)
        median_time = statistics.median(times)
        min_time = min(times)
        max_time = max(times)
        std_dev = statistics.stdev(times) if len(times) > 1 else 0
        success_rate = sum(results) / len(results) * 100
        
        benchmark_result = {
            'success': True,
            'pdf_path': pdf_path,
            'iterations': iterations,
            'times': times,
            'statistics': {
                'average_time': avg_time,
                'median_time': median_time,
                'min_time': min_time,
                'max_time': max_time,
                'std_deviation': std_dev,
                'success_rate': success_rate
            }
        }
        
        self.logger.info(f"Benchmark completed. Average: {avg_time:.2f}s, Success rate: {success_rate:.1f}%")
        
        return benchmark_result
    
    def benchmark_batch_processing(self, pdf_directory: str, max_files: int = None) -> Dict[str, Any]:
        """Benchmark batch processing of multiple PDFs."""
        pdf_dir = Path(pdf_directory)
        
        if not pdf_dir.exists():
            return {'success': False, 'error': f'Directory not found: {pdf_directory}'}
        
        # Find PDF files
        pdf_files = list(pdf_dir.glob('*.pdf'))
        if max_files:
            pdf_files = pdf_files[:max_files]
        
        if not pdf_files:
            return {'success': False, 'error': 'No PDF files found in directory'}
        
        self.logger.info(f"Benchmarking batch processing: {len(pdf_files)} files")
        
        start_time = time.time()
        processing_times = []
        file_sizes = []
        results = []
        
        for i, pdf_path in enumerate(pdf_files):
            file_start = time.time()
            
            try:
                # Get file size
                file_size = os.path.getsize(pdf_path)
                file_sizes.append(file_size)
                
                # Process the PDF
                result = self.extractor.process_single_pdf(str(pdf_path))
                file_end = time.time()
                
                processing_time = file_end - file_start
                processing_times.append(processing_time)
                results.append(result is not None)
                
                self.logger.debug(f"File {i+1}/{len(pdf_files)}: {processing_time:.2f}s")
                
            except Exception as e:
                self.logger.error(f"Error processing {pdf_path}: {e}")
                processing_times.append(0)
                results.append(False)
        
        total_time = time.time() - start_time
        
        # Calculate statistics
        successful_times = [t for t, success in zip(processing_times, results) if success and t > 0]
        
        if not successful_times:
            return {'success': False, 'error': 'No successful processing times recorded'}
        
        batch_result = {
            'success': True,
            'directory': pdf_directory,
            'total_files': len(pdf_files),
            'successful_files': len(successful_times),
            'failed_files': len(pdf_files) - len(successful_times),
            'total_time': total_time,
            'statistics': {
                'average_time_per_file': statistics.mean(successful_times),
                'median_time_per_file': statistics.median(successful_times),
                'min_time': min(successful_times),
                'max_time': max(successful_times),
                'std_deviation': statistics.stdev(successful_times) if len(successful_times) > 1 else 0,
                'success_rate': len(successful_times) / len(pdf_files) * 100,
                'throughput_files_per_minute': len(successful_times) / (total_time / 60) if total_time > 0 else 0
            },
            'file_statistics': {
                'average_file_size': statistics.mean(file_sizes) if file_sizes else 0,
                'total_size_mb': sum(file_sizes) / (1024 * 1024),
                'processing_speed_mb_per_minute': (sum(file_sizes) / (1024 * 1024)) / (total_time / 60) if total_time > 0 else 0
            }
        }
        
        self.logger.info(f"Batch benchmark completed in {total_time:.2f}s")
        self.logger.info(f"Throughput: {batch_result['statistics']['throughput_files_per_minute']:.1f} files/min")
        
        return batch_result


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Batch Processing Performance Test Suite")
    parser.add_argument("path", help="Path to PDF file or directory")
    parser.add_argument("--mode", choices=['single', 'batch'], default='single',
                       help="Benchmark mode: single file or batch processing")
    parser.add_argument("--iterations", type=int, default=5,
                       help="Number of iterations for single file benchmark")
    parser.add_argument("--max-files", type=int, help="Maximum number of files for batch benchmark")
    parser.add_argument("--output", help="Output file for results (JSON)")
    parser.add_argument("--debug", action='store_true', help="Enable debug mode")
    args = parser.parse_args()
    
    tester = TestBatchProcessing(debug_mode=args.debug)
    
    if args.mode == 'single':
        if not os.path.isfile(args.path):
            print(f"Error: File not found: {args.path}")
            return
        
        result = tester.benchmark_single_pdf_processing(args.path, args.iterations)
        
        if result['success']:
            stats = result['statistics']
            print(f"\nSingle PDF Benchmark Results:")
            print(f"Average time: {stats['average_time']:.2f}s")
            print(f"Median time: {stats['median_time']:.2f}s")
            print(f"Min/Max time: {stats['min_time']:.2f}s / {stats['max_time']:.2f}s")
            print(f"Standard deviation: {stats['std_deviation']:.2f}s")
            print(f"Success rate: {stats['success_rate']:.1f}%")
        else:
            print(f"Benchmark failed: {result.get('error', 'Unknown error')}")
    
    elif args.mode == 'batch':
        if not os.path.isdir(args.path):
            print(f"Error: Directory not found: {args.path}")
            return
        
        result = tester.benchmark_batch_processing(args.path, args.max_files)
        
        if result['success']:
            stats = result['statistics']
            file_stats = result['file_statistics']
            print(f"\nBatch Processing Benchmark Results:")
            print(f"Total files: {result['total_files']}")
            print(f"Successful: {result['successful_files']}")
            print(f"Failed: {result['failed_files']}")
            print(f"Total time: {result['total_time']:.2f}s")
            print(f"Average time per file: {stats['average_time_per_file']:.2f}s")
            print(f"Throughput: {stats['throughput_files_per_minute']:.1f} files/min")
            print(f"Processing speed: {file_stats['processing_speed_mb_per_minute']:.1f} MB/min")
            print(f"Success rate: {stats['success_rate']:.1f}%")
        else:
            print(f"Benchmark failed: {result.get('error', 'Unknown error')}")
    
    # Save results if output file specified
    if args.output and 'result' in locals():
        try:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            print(f"\nResults saved to: {args.output}")
        except Exception as e:
            print(f"Error saving results: {e}")


if __name__ == "__main__":
    main() 