# ICLEAN

Python CLI tool for cleaning up unused imports <br>
(either user defined, coming from the standard or third party library)

#### Requires Python 3.10+

## Installation


Via pip:
```console
$ pip install iclean
```

From main branch:
```console
$ git clone https://github.com/kaliv0/iclean.git
$ cd iclean 
$ pip install .
```

## Example


To run the tool type <i>iclean</i> followed by target path and options
```console
$ iclean ../test --skip foo.py --verbose
```
